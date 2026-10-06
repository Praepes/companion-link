from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceData
from .const import EVENT_COMMAND
from .entity import XperiaTouchEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: DeviceData = hass.data["xperia_touch"][entry.entry_id]
    async_add_entities([XperiaTouchBrightness(hass, data)])


class XperiaTouchBrightness(XperiaTouchEntity, NumberEntity):
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, hass, coordinator) -> None:
        super().__init__(coordinator, "screen_brightness", "屏幕亮度", "mdi:brightness-6")
        self.hass = hass

    @property
    def native_value(self):
        value = self.coordinator.values.get("screen_brightness")
        if not isinstance(value, (int, float)) or value < 1:
            return None
        return value

    @property
    def available(self) -> bool:
        return self.coordinator.available and bool(self.coordinator.values.get("brightness_control_available", False))

    async def async_set_native_value(self, value: float) -> None:
        self.hass.bus.async_fire(EVENT_COMMAND, {"command": "brightness", "value": int(value)})
