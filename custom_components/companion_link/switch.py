from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceData
from .const import DOMAIN
from .entity import CompanionLinkEntity, add_alarm_entities, get_alarm


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: DeviceData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CompanionLinkScreenSwitch(hass, data)])
    add_alarm_entities(
        hass,
        entry,
        data,
        async_add_entities,
        lambda alarm: [
            CompanionLinkAlarmSwitch(data, alarm["id"], "enabled", "启用"),
            CompanionLinkAlarmSwitch(data, alarm["id"], "ring_on_makeup_workdays", "补班日响铃"),
        ],
    )


class CompanionLinkScreenSwitch(CompanionLinkEntity, SwitchEntity):
    def __init__(self, hass, coordinator) -> None:
        super().__init__(coordinator, "screen_awake", "屏幕唤醒", "mdi:monitor")
        self.hass = hass

    @property
    def is_on(self):
        return bool(self.coordinator.values.get("screen_awake", False))

    @property
    def available(self):
        # A switch exposes both directions. Hide it unless both actions are
        # supported so HA cannot request a screen sleep the device cannot do.
        return self.coordinator.available and bool(
            self.coordinator.values.get("screen_wake_available", False)
            and self.coordinator.values.get("screen_sleep_available", False)
        )

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.send_command("wake")

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.send_command("sleep")


class CompanionLinkAlarmSwitch(CompanionLinkEntity, SwitchEntity):
    """Enable or configure an individual alarm."""

    def __init__(self, coordinator, alarm_id, field: str, name: str) -> None:
        self.alarm_id = alarm_id
        self.field = field
        super().__init__(coordinator, f"alarm_{alarm_id}_{field}", f"闹钟 {alarm_id} {name}", "mdi:alarm-check")

    @property
    def is_on(self):
        alarm = get_alarm(self.coordinator, self.alarm_id)
        return bool(alarm and alarm.get(self.field, False))

    @property
    def available(self):
        return super().available and get_alarm(self.coordinator, self.alarm_id) is not None

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.send_command("update_alarm", id=self.alarm_id, **{self.field: True})

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.send_command("update_alarm", id=self.alarm_id, **{self.field: False})
