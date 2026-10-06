from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceData
from .const import DOMAIN
from .entity import MorningPanelEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: DeviceData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        MorningPanelSensor(data, "battery_percent", "电量", "mdi:battery", SensorDeviceClass.BATTERY, PERCENTAGE),
        MorningPanelSensor(data, "screen_brightness", "屏幕亮度", "mdi:brightness-6", None, PERCENTAGE),
        MorningPanelSensor(data, "network_type", "网络类型", "mdi:wifi", None, None),
        MorningPanelSensor(data, "app_version", "应用版本", "mdi:application", None, None),
        MorningPanelSensor(data, "android_version", "Android 版本", "mdi:android", None, None),
        MorningPanelSensor(data, "device_model", "设备型号", "mdi:projector", None, None),
        MorningPanelSensor(data, "display_resolution", "屏幕分辨率", "mdi:monitor", None, None),
        MorningPanelSensor(data, "display_density_dpi", "屏幕密度", "mdi:monitor", None, "dpi"),
        MorningPanelSensor(data, "uptime_seconds", "运行时间", "mdi:timer-outline", None, UnitOfTime.SECONDS),
        MorningPanelSensor(data, "next_alarm", "下次闹钟", "mdi:alarm", SensorDeviceClass.TIMESTAMP, None),
        MorningPanelSensor(data, "next_alarm_label", "下次闹钟名称", "mdi:label-outline", None, None),
        MorningPanelSensor(data, "capabilities", "可用控制能力", "mdi:check-decagram", None, None),
        MorningPanelSensor(data, "command_result", "最近控制结果", "mdi:check-circle-outline", None, None),
    ])


class MorningPanelSensor(MorningPanelEntity, SensorEntity):
    def __init__(self, coordinator, key, name, icon, device_class, unit) -> None:
        super().__init__(coordinator, key, name, icon)
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        if unit == PERCENTAGE:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.key == "command_result":
            result = self.coordinator.command_result
            if result is None:
                return None
            return ("成功：" if result.get("success") else "失败：") + str(result.get("message", "未知结果"))
        value = self.coordinator.values.get(self.key)
        if self.key == "capabilities" and isinstance(value, list):
            return ", ".join(value)
        if self.key in ("battery_percent", "screen_brightness") and isinstance(value, (int, float)) and value < 0:
            return None
        return value

    @property
    def available(self) -> bool:
        if self.key == "command_result":
            return self.coordinator.command_result is not None
        return self.coordinator.available and self.key in self.coordinator.values

