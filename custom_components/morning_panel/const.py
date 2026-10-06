from homeassistant.const import Platform

DOMAIN = "morning_panel"
DEVICE_ID = "morning_panel_display"
EVENT_UPDATE = "morning_panel_update"
EVENT_COMMAND = "morning_panel_command"
EVENT_COMMAND_RESULT = "morning_panel_command_result"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.BUTTON]
