from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class CompanionLinkEntity(Entity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key: str, name: str, icon: str | None = None) -> None:
        self.coordinator = coordinator
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_id}_{key}"
        self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            name=self.coordinator.values.get("device_name", "Android device"),
            manufacturer=self.coordinator.values.get("manufacturer", "Android"),
            model=self.coordinator.values.get("device_model", "Unknown model"),
            sw_version=self.coordinator.values.get("app_version"),
        )

    @property
    def available(self) -> bool:
        return self.coordinator.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.add_listener(self.async_write_ha_state))
