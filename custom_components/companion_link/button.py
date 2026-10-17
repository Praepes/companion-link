from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError

from . import DeviceData
from .const import DOMAIN
from .entity import CompanionLinkEntity, add_alarm_entities, add_message_entities


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: DeviceData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        CompanionLinkWakeButton(data),
        CompanionLinkRefreshRssButton(data),
        CompanionLinkAddAlarmButton(data),
        CompanionLinkAlarmButton(hass, data, "snooze_alarm", "贪睡闹钟 10 分钟", "mdi:alarm-snooze"),
        CompanionLinkAlarmButton(hass, data, "stop_alarm", "停止闹钟", "mdi:alarm-off"),
    ])
    add_message_entities(entry, data, async_add_entities, lambda d: [CompanionLinkSendMessageButton(d)])
    projector_added = False

    def add_projector_buttons():
        nonlocal projector_added
        if not projector_added and (data.values.get("input_source_supported", False)
                                    or "G1109" in str(data.values.get("device_model", ""))):
            projector_added = True
            async_add_entities([
                CompanionLinkProjectorButton(data, "sleep", "休眠并关闭投影", "mdi:projector-off"),
                CompanionLinkProjectorButton(data, "wake", "唤醒并恢复投影", "mdi:projector"),
            ])

    entry.async_on_unload(data.add_listener(add_projector_buttons))
    add_projector_buttons()
    add_alarm_entities(
        hass,
        entry,
        data,
        async_add_entities,
        lambda alarm: [CompanionLinkDeleteAlarmButton(data, alarm["id"])],
    )


class CompanionLinkProjectorButton(CompanionLinkEntity, ButtonEntity):
    def __init__(self, coordinator, command: str, name: str, icon: str) -> None:
        super().__init__(coordinator, f"projector_{command}", name, icon)
        self.command = command

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.values.get("projector_control_available", False))

    async def async_press(self) -> None:
        result = await self.coordinator._async_send_command(self.command, {})
        if not result.get("success", False):
            raise HomeAssistantError(result.get("message", "Projector power command failed"))


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


class CompanionLinkAddAlarmButton(CompanionLinkEntity, ButtonEntity):
    """Create a disabled starter alarm that can be configured in entities."""

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "add_alarm", "新增闹钟（默认关闭）", "mdi:alarm-plus")

    async def async_press(self) -> None:
        self.coordinator.send_command(
            "add_alarm",
            hour=7,
            minute=0,
            label="新闹钟",
            repeat_mask=0,
            enabled=False,
            schedule_mode=0,
            ring_on_makeup_workdays=False,
        )


class CompanionLinkDeleteAlarmButton(CompanionLinkEntity, ButtonEntity):
    """Delete an alarm from the app."""

    def __init__(self, coordinator, alarm_id) -> None:
        self.alarm_id = alarm_id
        super().__init__(coordinator, f"delete_alarm_{alarm_id}", f"删除闹钟 {alarm_id}", "mdi:alarm-remove")

    @property
    def available(self) -> bool:
        return self.coordinator.available and any(
            str(alarm.get("id")) == str(self.alarm_id) for alarm in self.coordinator.alarms
        )

    async def async_press(self) -> None:
        self.coordinator.send_command("delete_alarm", id=self.alarm_id)


class CompanionLinkSendMessageButton(CompanionLinkEntity, ButtonEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator, "send_message", "发送留言", "mdi:message-arrow-right-outline")

    @property
    def available(self):
        return super().available and bool(self.coordinator.values.get("message_supported", False))

    async def async_press(self):
        result = await self.coordinator._async_send_command("send_message", {})
        if not result.get("success", False):
            raise HomeAssistantError(result.get("message", "留言发送失败"))
