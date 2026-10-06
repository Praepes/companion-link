from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import entity_registry as er

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


def add_alarm_entities(hass, entry, coordinator, async_add_entities, factory) -> None:
    """Add entities for current alarms, later alarms, and remove deleted alarms."""
    entities_by_id: dict[str, list[CompanionLinkEntity]] = {}

    def sync_alarms() -> None:
        current_ids = {str(alarm.get("id")) for alarm in coordinator.alarms}
        entities = []
        for alarm in coordinator.alarms:
            alarm_id = str(alarm.get("id"))
            if alarm_id in entities_by_id:
                continue
            alarm_entities = factory(alarm)
            entities_by_id[alarm_id] = alarm_entities
            entities.extend(alarm_entities)
        if entities:
            async_add_entities(entities)

        registry = er.async_get(hass)
        for alarm_id in entities_by_id.keys() - current_ids:
            for entity in entities_by_id.pop(alarm_id):
                if entity.entity_id is None:
                    continue
                if registry.async_get(entity.entity_id):
                    registry.async_remove(entity.entity_id)
                else:
                    hass.async_create_task(entity.async_remove(force_remove=True))

        # Also clean up alarm entities left in the registry by an older version
        # that kept deleted alarms as unavailable entities.
        if coordinator.last_update is not None:
            unique_prefix = f"{DOMAIN}_{coordinator.device_id}_"
            for registry_entry in tuple(registry.entities.values()):
                if registry_entry.config_entry_id != entry.entry_id:
                    continue
                unique_id = registry_entry.unique_id
                if not unique_id.startswith(unique_prefix):
                    continue
                key = unique_id[len(unique_prefix):]
                if key.startswith("alarm_"):
                    alarm_id = key[len("alarm_"):].split("_", 1)[0]
                elif key.startswith("delete_alarm_"):
                    alarm_id = key[len("delete_alarm_"):]
                else:
                    continue
                if alarm_id not in current_ids:
                    registry.async_remove(registry_entry.entity_id)

    unsubscribe = coordinator.add_listener(sync_alarms)
    hass.data[DOMAIN].setdefault(f"_platform_unsubs_{entry.entry_id}", []).append(unsubscribe)
    sync_alarms()


def get_alarm(coordinator, alarm_id):
    """Find an alarm in the latest device state."""
    return next((alarm for alarm in coordinator.alarms if str(alarm.get("id")) == str(alarm_id)), None)
