from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceData
from .const import DOMAIN
from .entity import CompanionLinkEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: DeviceData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CompanionLinkScreenSwitch(hass, data)])


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
