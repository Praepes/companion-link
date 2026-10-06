"""Home Assistant integration for Companion Link."""

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import CONF_DEVICE_ID, DOMAIN, EVENT_COMMAND, EVENT_COMMAND_RESULT, EVENT_UPDATE, PLATFORMS

_LOGGER = logging.getLogger(__name__)


class DeviceData:
    def __init__(self, hass: HomeAssistant, device_id: str) -> None:
        self.hass = hass
        self.device_id = device_id
        self.values: dict = {}
        self.listeners = set()
        self.last_update = None
        self.command_result = None
        self.command_result_at = None
        self.alarms = []
        self.rss_sources = []
        self.rss_articles = []
        self.rss_refreshed_at = None
        self.rss_refresh_error = ""

    @callback
    def async_update(self, event: Event) -> None:
        if event.data.get(CONF_DEVICE_ID) != self.device_id:
            return
        self.values = dict(event.data)
        if isinstance(event.data.get("alarms"), list):
            self.alarms = event.data["alarms"]
        if isinstance(event.data.get("rss_sources"), list):
            self.rss_sources = event.data["rss_sources"]
        self.rss_articles = event.data.get("rss_articles", self.rss_articles)
        self.rss_refreshed_at = event.data.get("rss_refreshed_at", self.rss_refreshed_at)
        self.rss_refresh_error = event.data.get("rss_refresh_error", self.rss_refresh_error)
        self.last_update = event.time_fired
        _LOGGER.debug("Received Companion Link status update")
        for listener in tuple(self.listeners):
            listener()

    @callback
    def async_command_result(self, event: Event) -> None:
        if event.data.get(CONF_DEVICE_ID) != self.device_id:
            return
        self.command_result = dict(event.data)
        payload = event.data.get("data", {})
        if isinstance(payload, dict):
            if isinstance(payload.get("alarms"), list):
                self.alarms = payload["alarms"]
            if isinstance(payload.get("rss_sources"), list):
                self.rss_sources = payload["rss_sources"]
            if isinstance(payload.get("rss_articles"), list):
                self.rss_articles = payload["rss_articles"]
            if "rss_refreshed_at" in payload:
                self.rss_refreshed_at = payload["rss_refreshed_at"]
            if "rss_refresh_error" in payload:
                self.rss_refresh_error = payload["rss_refresh_error"]
        self.command_result_at = event.time_fired
        _LOGGER.info("Companion Link command %s: %s", self.command_result.get("command"),
                     "success" if self.command_result.get("success") else "failed")
        for listener in tuple(self.listeners):
            listener()

    @callback
    def async_tick(self, now) -> None:
        for listener in tuple(self.listeners):
            listener()

    @property
    def available(self) -> bool:
        if self.last_update is None:
            return False
        return (dt_util.utcnow() - self.last_update).total_seconds() < 90

    @callback
    def add_listener(self, listener):
        self.listeners.add(listener)
        return lambda: self.listeners.discard(listener)

    @callback
    def send_command(self, command: str, **values) -> None:
        self.hass.bus.async_fire(
            EVENT_COMMAND,
            {CONF_DEVICE_ID: self.device_id, "command": command, **values},
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device = DeviceData(hass, entry.data[CONF_DEVICE_ID])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device
    unsubscribe = hass.bus.async_listen(EVENT_UPDATE, device.async_update)
    hass.data[DOMAIN][f"unsubscribe_{entry.entry_id}"] = unsubscribe
    result_unsubscribe = hass.bus.async_listen(EVENT_COMMAND_RESULT, device.async_command_result)
    hass.data[DOMAIN][f"result_unsubscribe_{entry.entry_id}"] = result_unsubscribe
    hass.data[DOMAIN][f"tick_{entry.entry_id}"] = async_track_time_interval(
        hass, device.async_tick, timedelta(seconds=30)
    )
    if not hass.data[DOMAIN].get("services_registered"):
        _register_services(hass)
        hass.data[DOMAIN]["services_registered"] = True
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _register_services(hass: HomeAssistant) -> None:
    schemas = {
        "get_alarms": vol.Schema({vol.Required("device_id"): str}),
        "add_alarm": vol.Schema({
            vol.Required("device_id"): str, vol.Required("hour"): vol.All(int, vol.Range(min=0, max=23)),
            vol.Required("minute"): vol.All(int, vol.Range(min=0, max=59)),
            vol.Optional("label", default="闹钟"): str, vol.Optional("repeat_mask", default=0): vol.All(int, vol.Range(min=0, max=127)),
            vol.Optional("enabled", default=True): bool, vol.Optional("schedule_mode", default=0): vol.In([0, 1]),
            vol.Optional("ring_on_makeup_workdays", default=False): bool,
        }),
        "update_alarm": vol.Schema({
            vol.Required("device_id"): str, vol.Required("id"): int,
            vol.Optional("hour"): vol.All(int, vol.Range(min=0, max=23)),
            vol.Optional("minute"): vol.All(int, vol.Range(min=0, max=59)),
            vol.Optional("label"): str, vol.Optional("repeat_mask"): vol.All(int, vol.Range(min=0, max=127)),
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
            device = next((item for key, item in hass.data.get(DOMAIN, {}).items()
                           if isinstance(item, DeviceData) and item.device_id == device_id), None)
            if device is None:
                _LOGGER.warning("Ignoring %s request for unknown Companion Link device", command)
                return
            values = dict(call.data)
            values.pop("device_id", None)
            if command == "set_rss_config" and isinstance(values.get("sources"), str):
                values["sources"] = [line.strip() for line in values["sources"].replace(",", "\n").splitlines() if line.strip()]
            elif command == "set_rss_config":
                values["sources"] = [str(line).strip() for line in values["sources"] if str(line).strip()]
            device.send_command(command, **values)
        return handle

    for command, schema in schemas.items():
        hass.services.async_register(DOMAIN, command, command_handler(command), schema=schema)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    data = hass.data[DOMAIN]
    for unsubscribe in data.pop(f"_platform_unsubs_{entry.entry_id}", []):
        unsubscribe()
    data.pop(f"unsubscribe_{entry.entry_id}")()
    data.pop(f"result_unsubscribe_{entry.entry_id}")()
    data.pop(f"tick_{entry.entry_id}")()
    data.pop(entry.entry_id)
    if not any(isinstance(item, DeviceData) for item in data.values()):
        for service in ("get_alarms", "add_alarm", "update_alarm", "delete_alarm",
                        "get_rss_config", "set_rss_config", "refresh_rss"):
            hass.services.async_remove(DOMAIN, service)
        data.pop("services_registered", None)
    return True
