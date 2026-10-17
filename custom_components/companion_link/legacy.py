"""Keep existing device-ID/event pairings working after the 3.1 upgrade."""

import asyncio
from uuid import uuid4

from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from . import DeviceData
from .const import CONF_DEVICE_ID, EVENT_COMMAND


class LegacyDeviceData(DeviceData):
    def __init__(self, hass, entry) -> None:
        super().__init__(hass, entry)
        self._pending = {}

    @property
    def available(self) -> bool:
        return self.last_update is not None and (dt_util.utcnow() - self.last_update).total_seconds() < 90

    @callback
    def async_update(self, event) -> None:
        if event.data.get(CONF_DEVICE_ID) != self.device_id:
            return
        self.values = dict(event.data)
        self._update_payload(event.data)
        self.last_update = event.time_fired
        self._notify()

    def _update_payload(self, payload) -> None:
        for field in ("alarms", "rss_sources", "rss_articles"):
            if isinstance(payload.get(field), list):
                setattr(self, field, payload[field])
        for field in ("rss_refreshed_at", "rss_refresh_error"):
            if field in payload:
                setattr(self, field, payload[field])

    def _notify(self) -> None:
        for listener in tuple(self.listeners):
            listener()

    @callback
    def async_command_result(self, event) -> None:
        if event.data.get(CONF_DEVICE_ID) != self.device_id:
            return
        self.command_result = dict(event.data)
        self.command_result_at = event.time_fired
        payload = event.data.get("data")
        if isinstance(payload, dict):
            self._update_payload(payload)
        future = self._pending.get(event.data.get("request_id"))
        if future is not None and not future.done():
            future.set_result(dict(event.data))
        self._notify()

    @callback
    def async_tick(self, _now) -> None:
        self._notify()

    @callback
    def send_command(self, command: str, **values) -> None:
        self.hass.bus.async_fire(EVENT_COMMAND, {CONF_DEVICE_ID: self.device_id, "command": command, **values})

    async def _async_send_command(self, command: str, values: dict) -> dict:
        request_id = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        self.send_command(command, **values, request_id=request_id)
        try:
            return await asyncio.wait_for(future, timeout=60)
        except asyncio.TimeoutError:
            result = {"command": command, "success": False, "message": "设备未在 60 秒内返回控制结果"}
            self.command_result = result
            self.command_result_at = dt_util.utcnow()
            self._notify()
            return result
        finally:
            self._pending.pop(request_id, None)

    def cancel_pending(self) -> None:
        for future in self._pending.values():
            future.cancel()
