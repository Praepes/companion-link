"""Home Assistant integration for Companion Link."""

import logging
from datetime import timedelta

from aiohttp import ClientError, ClientTimeout
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (CONF_ACCESS_TOKEN, CONF_DEVICE_ID, CONF_HOST, DOMAIN,
                    EVENT_COMMAND_RESULT, EVENT_UPDATE, PLATFORMS)

_LOGGER = logging.getLogger(__name__)
POLL_INTERVAL = timedelta(seconds=10)


class DeviceData:
    """Cached state and authenticated local API client for one Android device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.device_id = entry.data[CONF_DEVICE_ID]
        self.host = entry.data.get(CONF_HOST, "")
        self.access_token = entry.data.get(CONF_ACCESS_TOKEN, "")
        self.values: dict = {}
        self.listeners = set()
        self.last_update = None
        self.command_result = None
        self.command_result_at = None
        self.alarms: list[dict] = []
        self.rss_sources: list[str] = []
        self.rss_articles: list[dict] = []
        self.rss_refreshed_at = None
        self.rss_refresh_error = ""

    async def async_poll(self, _now=None) -> None:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"http://{self.host}:8765/api/status",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=ClientTimeout(total=8),
            ) as response:
                response.raise_for_status()
                values = await response.json()
            if values.get(CONF_DEVICE_ID) != self.device_id:
                _LOGGER.error("Companion Link device identity changed for %s", self.host)
                return
            self.alarms = values.get("alarms", []) if isinstance(values.get("alarms"), list) else []
            raw_sources = values.get("rss_sources", [])
            self.rss_sources = [
                str(item.get("url", "")) if isinstance(item, dict) else str(item)
                for item in raw_sources
                if (item.get("url") if isinstance(item, dict) else item)
            ] if isinstance(raw_sources, list) else []
            self.rss_articles = values.get("rss_articles", []) if isinstance(values.get("rss_articles"), list) else []
            self.rss_refreshed_at = values.get("rss_refreshed_at")
            self.rss_refresh_error = values.get("rss_refresh_error", "")
            values["rss_sources"] = self.rss_sources
            self.values = values
            self.last_update = dt_util.utcnow()
            for listener in tuple(self.listeners):
                listener()
        except (ClientError, OSError, TimeoutError, ValueError) as error:
            _LOGGER.debug("Unable to read Companion Link device at %s: %s", self.host, error)

    @property
    def available(self) -> bool:
        return self.last_update is not None and (dt_util.utcnow() - self.last_update).total_seconds() < 35

    @callback
    def add_listener(self, listener):
        self.listeners.add(listener)
        return lambda: self.listeners.discard(listener)

    @callback
    def send_command(self, command: str, **values) -> None:
        self.hass.async_create_task(self._async_send_command(command, values))

    async def _async_send_command(self, command: str, values: dict) -> dict:
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                f"http://{self.host}:8765/api/command",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={"command": command, **values},
                timeout=ClientTimeout(total=60),
            ) as response:
                response.raise_for_status()
                result = await response.json()
                self.command_result = result
                self.command_result_at = dt_util.utcnow()
            await self.async_poll()
            for listener in tuple(self.listeners):
                listener()
        except (ClientError, OSError, TimeoutError, ValueError) as error:
            _LOGGER.warning("Companion Link command %s failed: %s", command, error)
            result = {"command": command, "success": False, "message": "无法连接设备"}
            self.command_result = result
            self.command_result_at = dt_util.utcnow()
            for listener in tuple(self.listeners):
                listener()
        return result


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.data.get(CONF_HOST) and entry.data.get(CONF_ACCESS_TOKEN):
        device = DeviceData(hass, entry)
    else:
        from .legacy import LegacyDeviceData
        device = LegacyDeviceData(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device
    if device.host and device.access_token:
        await device.async_poll()
        unsubscribe = async_track_time_interval(hass, device.async_poll, POLL_INTERVAL)
    else:
        state_unsub = hass.bus.async_listen(EVENT_UPDATE, device.async_update)
        result_unsub = hass.bus.async_listen(EVENT_COMMAND_RESULT, device.async_command_result)
        tick_unsub = async_track_time_interval(hass, device.async_tick, timedelta(seconds=30))

        def unsubscribe():
            state_unsub()
            result_unsub()
            tick_unsub()
            device.cancel_pending()

    hass.data[DOMAIN][f"poll_{entry.entry_id}"] = unsubscribe
    if not hass.data[DOMAIN].get("services_registered"):
        _register_services(hass)
        hass.data[DOMAIN]["services_registered"] = True
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version > 2:
        return False
    if entry.version < 2:
        # Version 1 entries retain their event transport and device/entity IDs.
        # Pairing the same device by IP later updates the existing entry in place.
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    data = hass.data[DOMAIN]
    data.pop(f"poll_{entry.entry_id}")()
    for unsubscribe in data.pop(f"_platform_unsubs_{entry.entry_id}", []):
        unsubscribe()
    data.pop(entry.entry_id)
    if not any(isinstance(item, DeviceData) for item in data.values()):
        for service in ("get_alarms", "add_alarm", "update_alarm", "delete_alarm",
                        "get_rss_config", "set_rss_config", "refresh_rss", "send_message"):
            hass.services.async_remove(DOMAIN, service)
        data.pop("services_registered", None)
    return True


def _register_services(hass: HomeAssistant) -> None:
    schemas = {
        "send_message": vol.Schema({
            vol.Required("device_id"): str,
            vol.Required("text"): vol.All(str, vol.Length(min=1, max=255)),
            vol.Optional("play_sound", default=False): bool,
        }),
        "get_alarms": vol.Schema({vol.Required("device_id"): str}),
        "add_alarm": vol.Schema({
            vol.Required("device_id"): str,
            vol.Required("hour"): vol.All(int, vol.Range(min=0, max=23)),
            vol.Required("minute"): vol.All(int, vol.Range(min=0, max=59)),
            vol.Optional("label", default="闹钟"): str,
            vol.Optional("repeat_mask", default=0): vol.All(int, vol.Range(min=0, max=127)),
            vol.Optional("enabled", default=True): bool,
            vol.Optional("schedule_mode", default=0): vol.In([0, 1]),
            vol.Optional("ring_on_makeup_workdays", default=False): bool,
        }),
        "update_alarm": vol.Schema({
            vol.Required("device_id"): str, vol.Required("id"): int,
            vol.Optional("hour"): vol.All(int, vol.Range(min=0, max=23)),
            vol.Optional("minute"): vol.All(int, vol.Range(min=0, max=59)),
            vol.Optional("label"): str,
            vol.Optional("repeat_mask"): vol.All(int, vol.Range(min=0, max=127)),
            vol.Optional("enabled"): bool, vol.Optional("schedule_mode"): vol.In([0, 1]),
            vol.Optional("ring_on_makeup_workdays"): bool,
        }),
        "delete_alarm": vol.Schema({vol.Required("device_id"): str, vol.Required("id"): int}),
        "get_rss_config": vol.Schema({vol.Required("device_id"): str}),
        "set_rss_config": vol.Schema({vol.Required("device_id"): str, vol.Required("sources"): vol.Any(str, list)}),
        "refresh_rss": vol.Schema({vol.Required("device_id"): str}),
    }

    def command_handler(command: str):
        @callback
        def handle(call):
            device_id = call.data["device_id"]
            device = next((item for item in hass.data.get(DOMAIN, {}).values()
                           if isinstance(item, DeviceData) and item.device_id == device_id), None)
            if device is None:
                _LOGGER.warning("Ignoring %s request for unknown Companion Link device", command)
                return
            values = dict(call.data)
            values.pop("device_id", None)
            if command == "set_rss_config":
                raw = values.get("sources", [])
                values["sources"] = [line.strip() for line in raw.replace(",", "\n").splitlines() if line.strip()] if isinstance(raw, str) else [str(line).strip() for line in raw if str(line).strip()]
            device.send_command(command, **values)
        return handle

    for command, schema in schemas.items():
        hass.services.async_register(DOMAIN, command, command_handler(command), schema=schema)
