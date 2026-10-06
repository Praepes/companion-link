from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

from .const import CONF_DEVICE_ID, DOMAIN
from .options_flow import CompanionLinkOptionsFlow


class CompanionLinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_DEVICE_ID): str})

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            if not device_id:
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Companion Link · {device_id[-6:]}",
                    data={CONF_DEVICE_ID: device_id},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Open the device management menu."""
        return CompanionLinkOptionsFlow()
