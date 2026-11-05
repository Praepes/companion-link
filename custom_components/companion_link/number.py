from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceData
from .const import DOMAIN
from homeassistant.exceptions import HomeAssistantError

from .entity import CompanionLinkEntity, add_optics_entities


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: DeviceData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CompanionLinkBrightness(hass, data)])
    add_optics_entities(entry, data, async_add_entities, lambda d: [CompanionLinkKeystone(d)])


class CompanionLinkBrightness(CompanionLinkEntity, NumberEntity):
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
        self.coordinator.send_command("brightness", value=int(value))


class CompanionLinkKeystone(CompanionLinkEntity, NumberEntity):
    _attr_native_min_value = -15
    _attr_native_max_value = 15
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "projector_keystone", "梯形校正", "mdi:perspective-less")

    @property
    def native_value(self):
        value = self.coordinator.values.get("projector_keystone")
        return value if isinstance(value, (int, float)) and -15 <= value <= 15 else None

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.values.get("projector_control_available", False))

    async def async_set_native_value(self, value: float) -> None:
        if not -15 <= value <= 15 or int(value) != value:
            raise HomeAssistantError("梯形校正必须是 -15 到 15 的整数")
        result = await self.coordinator._async_send_command("keystone", {"value": int(value)})
        if not result.get("success", False):
            raise HomeAssistantError(result.get("message", "Keystone command failed"))
