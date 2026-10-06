"""Home Assistant integration for Morning Panel."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_COMMAND_RESULT, EVENT_UPDATE, PLATFORMS

_LOGGER = logging.getLogger(__name__)


class DeviceData:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.values: dict = {}
        self.listeners = set()
        self.last_update = None
        self.command_result = None
        self.command_result_at = None

    @callback
    def async_update(self, event: Event) -> None:
        self.values = dict(event.data)
        self.last_update = event.time_fired
        _LOGGER.debug("Received Morning Panel status update")
        for listener in tuple(self.listeners):
            listener()

    @callback
    def async_command_result(self, event: Event) -> None:
        self.command_result = dict(event.data)
        self.command_result_at = event.time_fired
        _LOGGER.info("Morning Panel command %s: %s", self.command_result.get("command"),
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device = DeviceData(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device
    unsubscribe = hass.bus.async_listen(EVENT_UPDATE, device.async_update)
    hass.data[DOMAIN][f"unsubscribe_{entry.entry_id}"] = unsubscribe
    result_unsubscribe = hass.bus.async_listen(EVENT_COMMAND_RESULT, device.async_command_result)
    hass.data[DOMAIN][f"result_unsubscribe_{entry.entry_id}"] = result_unsubscribe
    hass.data[DOMAIN][f"tick_{entry.entry_id}"] = async_track_time_interval(
        hass, device.async_tick, timedelta(seconds=30)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    data = hass.data[DOMAIN]
    data.pop(f"unsubscribe_{entry.entry_id}")()
    data.pop(f"result_unsubscribe_{entry.entry_id}")()
    data.pop(f"tick_{entry.entry_id}")()
    data.pop(entry.entry_id)
    return True
