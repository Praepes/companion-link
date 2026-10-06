"""Home Assistant UI for managing Morning Panel alarms and RSS feeds."""

from __future__ import annotations

from collections.abc import Mapping

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import DOMAIN

WEEKDAYS = (
    ("mon", "周一"),
    ("tue", "周二"),
    ("wed", "周三"),
    ("thu", "周四"),
    ("fri", "周五"),
    ("sat", "周六"),
    ("sun", "周日"),
)


class CompanionLinkOptionsFlow(config_entries.OptionsFlow):
    """Manage alarms and RSS directly from the integration config screen."""

    def __init__(self) -> None:
        self._selected_alarm: dict | None = None
        self._finish_step: str | None = None

    @property
    def device(self):
        """Return the coordinator for this config entry."""
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    async def async_step_init(self, user_input=None):
        """Show available device configuration tasks."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "view_alarms",
                "add_alarm",
                "edit_alarm",
                "delete_alarm",
                "view_rss",
                "configure_rss",
                "refresh_rss",
            ],
            description_placeholders={
                "device_name": self.device.values.get("device_name", "Morning Panel") if self.device else "Morning Panel",
            },
        )

    async def async_step_view_alarms(self, user_input=None):
        """Display the current alarm list."""
        if user_input is not None:
            return await self.async_step_init()
        alarms = self.device.alarms if self.device else []
        return self.async_show_form(
            step_id="view_alarms",
            data_schema=vol.Schema({}),
            description_placeholders={"alarms": _format_alarms(alarms)},
        )

    async def async_step_add_alarm(self, user_input=None):
        """Create an alarm on the app."""
        if user_input is not None:
            repeat_type = user_input["repeat_type"]
            days = user_input["days"]
            if repeat_type == "weekly" and not days:
                return self.async_show_form(
                    step_id="add_alarm",
                    data_schema=_alarm_schema(values=user_input),
                    errors={"base": "select_weekdays"},
                )
            if self.device is None:
                return self.async_abort(reason="device_unavailable")
            self.device.send_command("add_alarm", **_alarm_command(user_input))
            return self._show_command_sent("闹钟新增请求已发送。")
        return self.async_show_form(step_id="add_alarm", data_schema=_alarm_schema())

    async def async_step_edit_alarm(self, user_input=None):
        """Select an existing alarm to edit."""
        if user_input is not None:
            alarm_id = int(user_input["id"])
            self._selected_alarm = _find_alarm(self.device, alarm_id)
            if self._selected_alarm is None:
                return self.async_abort(reason="alarm_not_found")
            return await self.async_step_edit_alarm_values()
        alarms = self.device.alarms if self.device else []
        if not alarms:
            return self.async_abort(reason="no_alarms")
        return self.async_show_form(
            step_id="edit_alarm",
            data_schema=vol.Schema({vol.Required("id"): _alarm_selector(alarms)}),
        )

    async def async_step_edit_alarm_values(self, user_input=None):
        """Save changes to the selected alarm."""
        if self._selected_alarm is None:
            return self.async_abort(reason="alarm_not_found")
        if user_input is not None:
            repeat_type = user_input["repeat_type"]
            days = user_input["days"]
            if repeat_type == "weekly" and not days:
                return self.async_show_form(
                    step_id="edit_alarm_values",
                    data_schema=_alarm_schema(self._selected_alarm, user_input),
                    errors={"base": "select_weekdays"},
                )
            if self.device is None:
                return self.async_abort(reason="device_unavailable")
            values = _alarm_command(user_input)
            values["id"] = self._selected_alarm["id"]
            self.device.send_command("update_alarm", **values)
            return self._show_command_sent("闹钟修改请求已发送。")
        return self.async_show_form(
            step_id="edit_alarm_values",
            data_schema=_alarm_schema(self._selected_alarm),
            description_placeholders={"alarm": _format_alarm(self._selected_alarm)},
        )

    async def async_step_delete_alarm(self, user_input=None):
        """Select an alarm to delete."""
        if user_input is not None:
            self._selected_alarm = _find_alarm(self.device, int(user_input["id"]))
            if self._selected_alarm is None:
                return self.async_abort(reason="alarm_not_found")
            return await self.async_step_confirm_delete()
        alarms = self.device.alarms if self.device else []
        if not alarms:
            return self.async_abort(reason="no_alarms")
        return self.async_show_form(
            step_id="delete_alarm",
            data_schema=vol.Schema({vol.Required("id"): _alarm_selector(alarms)}),
        )

    async def async_step_confirm_delete(self, user_input=None):
        """Confirm deletion before sending it to the app."""
        if self._selected_alarm is None:
            return self.async_abort(reason="alarm_not_found")
        if user_input is not None:
            if not user_input["confirm"]:
                return await self.async_step_init()
            if self.device is None:
                return self.async_abort(reason="device_unavailable")
            self.device.send_command("delete_alarm", id=self._selected_alarm["id"])
            return self._show_command_sent("闹钟删除请求已发送。")
        return self.async_show_form(
            step_id="confirm_delete",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"alarm": _format_alarm(self._selected_alarm)},
        )

    async def async_step_view_rss(self, user_input=None):
        """Show current RSS sources and refresh status."""
        if user_input is not None:
            return await self.async_step_init()
        device = self.device
        sources = device.rss_sources if device else []
        refreshed_at = device.rss_refreshed_at if device else None
        refresh_error = device.rss_refresh_error if device else ""
        articles = device.rss_articles if device else []
        return self.async_show_form(
            step_id="view_rss",
            data_schema=vol.Schema({}),
            description_placeholders={
                "sources": "\n".join(f"- {source}" for source in sources) or "尚未上报 RSS 来源。",
                "article_count": str(len(articles)),
                "refreshed_at": _format_timestamp(refreshed_at),
                "refresh_error": refresh_error or "无",
            },
        )

    async def async_step_configure_rss(self, user_input=None):
        """Set RSS sources on the app."""
        if user_input is not None:
            if self.device is None:
                return self.async_abort(reason="device_unavailable")
            sources = [line.strip() for line in user_input["sources"].replace(",", "\n").splitlines() if line.strip()]
            self.device.send_command("set_rss_config", sources=sources)
            return self._show_command_sent("RSS 来源配置请求已发送。")
        current = self.device.rss_sources if self.device else []
        return self.async_show_form(
            step_id="configure_rss",
            data_schema=vol.Schema(
                {
                    vol.Required("sources", default="\n".join(current)): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    )
                }
            ),
        )

    async def async_step_refresh_rss(self, user_input=None):
        """Request an RSS refresh from the app."""
        if self.device is None:
            return self.async_abort(reason="device_unavailable")
        self.device.send_command("refresh_rss")
        return self._show_command_sent("RSS 刷新请求已发送。")

    async def async_step_command_sent(self, user_input=None):
        """Show where to check the app's command result."""
        if user_input is not None:
            return self.async_abort(reason="finished")
        return self.async_show_form(
            step_id="command_sent",
            data_schema=vol.Schema({vol.Required("done", default=True): bool}),
            description_placeholders={"message": self._finish_step or "请求已发送。"},
        )

    def _show_command_sent(self, message: str):
        self._finish_step = message
        return self.async_show_form(
            step_id="command_sent",
            data_schema=vol.Schema({vol.Required("done", default=True): bool}),
            description_placeholders={"message": message},
        )


def _alarm_selector(alarms: list[dict]):
    """Create a dropdown with readable alarm labels."""
    options = [
        {"value": str(alarm["id"]), "label": _format_alarm(alarm)}
        for alarm in alarms
    ]
    return selector.SelectSelector(
        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
    )


def _alarm_schema(alarm: Mapping | None = None, values: Mapping | None = None) -> vol.Schema:
    """Build the shared create/edit alarm form."""
    alarm = alarm or {}
    values = values or {}
    repeat_type = "workdays" if alarm.get("schedule_mode") == 1 else "weekly" if alarm.get("repeat_mask", 0) else "once"
    selected_days = [
        day
        for index, (day, _) in enumerate(WEEKDAYS)
        if alarm.get("repeat_mask", 0) & (1 << index)
    ]
    return vol.Schema(
        {
            vol.Required("hour", default=values.get("hour", alarm.get("hour", 7))): vol.All(int, vol.Range(min=0, max=23)),
            vol.Required("minute", default=values.get("minute", alarm.get("minute", 0))): vol.All(int, vol.Range(min=0, max=59)),
            vol.Required("label", default=values.get("label", alarm.get("label", "闹钟"))): str,
            vol.Required("repeat_type", default=values.get("repeat_type", repeat_type)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "once", "label": "单次"},
                        {"value": "weekly", "label": "每周"},
                        {"value": "workdays", "label": "工作日"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("days", default=values.get("days", selected_days)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": day, "label": label} for day, label in WEEKDAYS],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required("enabled", default=values.get("enabled", alarm.get("enabled", True))): bool,
            vol.Required("ring_on_makeup_workdays", default=values.get("ring_on_makeup_workdays", alarm.get("ring_on_makeup_workdays", False))): bool,
        }
    )


def _alarm_command(user_input: dict) -> dict:
    """Convert the friendly repeat controls to the app's alarm fields."""
    repeat_type = user_input["repeat_type"]
    day_bits = {day: 1 << index for index, (day, _) in enumerate(WEEKDAYS)}
    repeat_mask = sum(day_bits[day] for day in user_input["days"]) if repeat_type == "weekly" else 0
    return {
        "hour": int(user_input["hour"]),
        "minute": int(user_input["minute"]),
        "label": user_input["label"],
        "repeat_mask": repeat_mask,
        "schedule_mode": 1 if repeat_type == "workdays" else 0,
        "enabled": user_input["enabled"],
        "ring_on_makeup_workdays": user_input["ring_on_makeup_workdays"],
    }


def _find_alarm(device, alarm_id: int) -> dict | None:
    if device is None:
        return None
    return next((alarm for alarm in device.alarms if alarm.get("id") == alarm_id), None)


def _format_alarms(alarms: list[dict]) -> str:
    return "\n".join(f"- {_format_alarm(alarm)}" for alarm in alarms) or "当前没有闹钟。"


def _format_alarm(alarm: Mapping) -> str:
    label = str(alarm.get("label", "闹钟")).replace("\n", " ").replace("\r", " ")
    for special in ("\\", "`", "*", "_", "[", "]", "(", ")"):
        label = label.replace(special, f"\\{special}")
    if alarm.get("schedule_mode") == 1:
        repeat = "工作日"
    elif alarm.get("repeat_mask", 0):
        repeat = "、".join(
            label for index, (_, label) in enumerate(WEEKDAYS)
            if alarm.get("repeat_mask", 0) & (1 << index)
        )
    else:
        repeat = "单次"
    enabled = "启用" if alarm.get("enabled") else "关闭"
    return f"ID {alarm.get('id')} · {int(alarm.get('hour', 0)):02d}:{int(alarm.get('minute', 0)):02d} · {label} · {repeat} · {enabled}"


def _format_timestamp(value) -> str:
    if not value:
        return "未知"
    try:
        timestamp = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        return dt_util.as_local(dt_util.utc_from_timestamp(timestamp)).strftime("%Y-%m-%d %H:%M:%S %Z")
    except (TypeError, ValueError, OverflowError):
        return str(value)
