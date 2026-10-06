from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceData
from .const import DOMAIN
from .entity import CompanionLinkEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: DeviceData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        CompanionLinkWakeButton(data),
        CompanionLinkRefreshRssButton(data),
        CompanionLinkAlarmButton(hass, data, "snooze_alarm", "贪睡闹钟 10 分钟", "mdi:alarm-snooze"),
        CompanionLinkAlarmButton(hass, data, "stop_alarm", "停止闹钟", "mdi:alarm-off"),
    ])


class CompanionLinkWakeButton(CompanionLinkEntity, ButtonEntity):
    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "screen_wake", "唤醒屏幕", "mdi:monitor-eye")

    @property
    def available(self) -> bool:
        return self.coordinator.available and bool(
            self.coordinator.values.get("screen_wake_available", False)
        )

    async def async_press(self) -> None:
        self.coordinator.send_command("wake")


class CompanionLinkRefreshRssButton(CompanionLinkEntity, ButtonEntity):
    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "refresh_rss", "刷新 RSS", "mdi:rss-sync")

    async def async_press(self) -> None:
        self.coordinator.send_command("refresh_rss")


class CompanionLinkAlarmButton(CompanionLinkEntity, ButtonEntity):
    def __init__(self, hass, coordinator, command: str, name: str, icon: str) -> None:
        super().__init__(coordinator, command, name, icon)
        self.hass = hass
        self.command = command

    @property
    def available(self) -> bool:
        return self.coordinator.available and bool(self.coordinator.values.get("alarm_ringing", False))

    async def async_press(self) -> None:
        self.coordinator.send_command(self.command)
