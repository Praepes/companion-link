from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceData
from .const import EVENT_COMMAND
from .entity import XperiaTouchEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: DeviceData = hass.data["xperia_touch"][entry.entry_id]
    async_add_entities([
        XperiaTouchAlarmButton(hass, data, "snooze_alarm", "贪睡闹钟 10 分钟", "mdi:alarm-snooze"),
        XperiaTouchAlarmButton(hass, data, "stop_alarm", "停止闹钟", "mdi:alarm-off"),
    ])


class XperiaTouchAlarmButton(XperiaTouchEntity, ButtonEntity):
    def __init__(self, hass, coordinator, command: str, name: str, icon: str) -> None:
        super().__init__(coordinator, command, name, icon)
        self.hass = hass
        self.command = command

    @property
    def available(self) -> bool:
        return self.coordinator.available and bool(self.coordinator.values.get("alarm_ringing", False))

    async def async_press(self) -> None:
        self.hass.bus.async_fire(EVENT_COMMAND, {"command": self.command})
