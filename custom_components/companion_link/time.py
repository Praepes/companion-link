from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceData
from .const import DOMAIN
from .entity import CompanionLinkEntity, add_alarm_entities, get_alarm


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up editable alarm time entities."""
    data: DeviceData = hass.data[DOMAIN][entry.entry_id]
    add_alarm_entities(
        hass,
        entry,
        data,
        async_add_entities,
        lambda alarm: [CompanionLinkAlarmTime(data, alarm["id"])],
    )


class CompanionLinkAlarmTime(CompanionLinkEntity, TimeEntity):
    """Set the hour and minute of one alarm."""

    def __init__(self, coordinator, alarm_id) -> None:
        self.alarm_id = alarm_id
        super().__init__(coordinator, f"alarm_{alarm_id}_time", f"闹钟 {alarm_id} 时间", "mdi:alarm")

    @property
    def native_value(self) -> time | None:
        alarm = get_alarm(self.coordinator, self.alarm_id)
        if alarm is None:
            return None
        return time(hour=int(alarm.get("hour", 0)), minute=int(alarm.get("minute", 0)))

    @property
    def available(self) -> bool:
        return super().available and get_alarm(self.coordinator, self.alarm_id) is not None

    async def async_set_value(self, value: time) -> None:
        self.coordinator.send_command(
            "update_alarm",
            id=self.alarm_id,
            hour=value.hour,
            minute=value.minute,
        )
