from __future__ import annotations

import re

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceData
from .const import DOMAIN
from .entity import CompanionLinkEntity, add_alarm_entities, get_alarm

WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
WEEKDAY_ALIASES = {
    **{name: index for index, name in enumerate(WEEKDAYS)},
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up editable alarm and RSS text entities."""
    data: DeviceData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CompanionLinkRssSources(data)])
    add_alarm_entities(
        hass,
        entry,
        data,
        async_add_entities,
        lambda alarm: [
            CompanionLinkAlarmName(data, alarm["id"]),
            CompanionLinkAlarmRepeat(data, alarm["id"]),
        ],
    )


class CompanionLinkRssSources(CompanionLinkEntity, TextEntity):
    """Edit feed URLs as a comma- or line-separated text value."""

    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 255

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "rss_sources_edit", "RSS 来源配置（逗号分隔）", "mdi:rss-box")

    @property
    def native_value(self) -> str:
        return ", ".join(self.coordinator.rss_sources)

    async def async_set_value(self, value: str) -> None:
        sources = [
            source.strip()
            for source in re.split(r"[,，\n\r]+", value)
            if source.strip()
        ]
        self.coordinator.send_command("set_rss_config", sources=sources)


class CompanionLinkAlarmName(CompanionLinkEntity, TextEntity):
    """Edit an alarm label."""

    _attr_mode = TextMode.TEXT
    _attr_native_min = 1
    _attr_native_max = 64

    def __init__(self, coordinator, alarm_id) -> None:
        self.alarm_id = alarm_id
        super().__init__(coordinator, f"alarm_{alarm_id}_name", f"闹钟 {alarm_id} 名称", "mdi:label-outline")

    @property
    def native_value(self) -> str | None:
        alarm = get_alarm(self.coordinator, self.alarm_id)
        return None if alarm is None else str(alarm.get("label", "闹钟"))

    @property
    def available(self) -> bool:
        return super().available and get_alarm(self.coordinator, self.alarm_id) is not None

    async def async_set_value(self, value: str) -> None:
        value = value.strip()
        if not value:
            raise HomeAssistantError("闹钟名称不能为空")
        self.coordinator.send_command("update_alarm", id=self.alarm_id, label=value)


class CompanionLinkAlarmRepeat(CompanionLinkEntity, TextEntity):
    """Edit alarm recurrence using Chinese weekday names or common presets."""

    _attr_mode = TextMode.TEXT
    _attr_native_min = 1
    _attr_native_max = 64

    def __init__(self, coordinator, alarm_id) -> None:
        self.alarm_id = alarm_id
        super().__init__(coordinator, f"alarm_{alarm_id}_repeat", f"闹钟 {alarm_id} 重复（单次/工作日/每天/星期）", "mdi:calendar-repeat")

    @property
    def native_value(self) -> str | None:
        alarm = get_alarm(self.coordinator, self.alarm_id)
        if alarm is None:
            return None
        if alarm.get("schedule_mode") == 1:
            return "工作日"
        mask = int(alarm.get("repeat_mask", 0))
        presets = {0: "单次", 31: "周一至周五", 96: "周末", 127: "每天"}
        if mask in presets:
            return presets[mask]
        return ", ".join(day for index, day in enumerate(WEEKDAYS) if mask & (1 << index))

    @property
    def available(self) -> bool:
        return super().available and get_alarm(self.coordinator, self.alarm_id) is not None

    async def async_set_value(self, value: str) -> None:
        normalized = value.strip().lower()
        presets = {
            "单次": (0, 0),
            "once": (0, 0),
            "工作日": (0, 1),
            "workdays": (0, 1),
            "每天": (127, 0),
            "daily": (127, 0),
            "周一至周五": (31, 0),
            "weekdays": (31, 0),
            "周末": (96, 0),
            "weekend": (96, 0),
        }
        if normalized in presets:
            repeat_mask, schedule_mode = presets[normalized]
        else:
            tokens = [token.strip().lower() for token in re.split(r"[,，、\s]+", normalized) if token.strip()]
            try:
                repeat_mask = 0
                for token in tokens:
                    repeat_mask |= 1 << WEEKDAY_ALIASES[token]
            except KeyError as err:
                supported = "、".join(WEEKDAYS)
                raise HomeAssistantError(
                    f"请输入单次、工作日、每天、周一至周五、周末，或以逗号分隔的星期（{supported}）"
                ) from err
            if not tokens:
                raise HomeAssistantError("每周重复至少需要选择一天")
            schedule_mode = 0
        self.coordinator.send_command(
            "update_alarm",
            id=self.alarm_id,
            repeat_mask=repeat_mask,
            schedule_mode=schedule_mode,
        )
