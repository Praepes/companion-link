from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceData
from .const import DOMAIN
from .entity import MorningPanelEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: DeviceData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        MorningPanelBinarySensor(data, "charging", "充电中", BinarySensorDeviceClass.BATTERY_CHARGING),
        MorningPanelBinarySensor(data, "network_connected", "网络已连接", BinarySensorDeviceClass.CONNECTIVITY),
        MorningPanelBinarySensor(data, "screen_awake", "屏幕唤醒", None),
        MorningPanelBinarySensor(data, "screen_wake_available", "屏幕唤醒可用", None),
        MorningPanelBinarySensor(data, "keep_screen_on", "主页保持常亮", None),
        MorningPanelBinarySensor(data, "alarm_ringing", "闹钟响铃中", None),
        MorningPanelBinarySensor(data, "root_available", "应用 Root 可用", None),
        MorningPanelBinarySensor(data, "screen_sleep_available", "屏幕休眠可用", None),
        MorningPanelBinarySensor(data, "brightness_control_available", "亮度控制可用", None),
    ])


class MorningPanelBinarySensor(MorningPanelEntity, BinarySensorEntity):
    def __init__(self, coordinator, key, name, device_class) -> None:
        super().__init__(coordinator, key, name, None)
        self._attr_device_class = device_class

    @property
    def is_on(self):
        return bool(self.coordinator.values.get(self.key, False))

    @property
    def available(self) -> bool:
        return self.coordinator.available and self.key in self.coordinator.values
