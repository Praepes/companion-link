from homeassistant.const import Platform

DOMAIN = "companion_link"
CONF_DEVICE_ID = "device_id"
EVENT_UPDATE = "companion_link_update"
EVENT_COMMAND = "companion_link_command"
EVENT_COMMAND_RESULT = "companion_link_command_result"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.BUTTON]
