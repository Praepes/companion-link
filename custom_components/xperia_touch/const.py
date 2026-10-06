from homeassistant.const import Platform

DOMAIN = "xperia_touch"
EVENT_UPDATE = "xperia_touch_update"
EVENT_COMMAND = "xperia_touch_command"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.BUTTON]
