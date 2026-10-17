"""Config flow for Companion Link."""

import asyncio
import ipaddress
import logging

import voluptuous as vol
from aiohttp import ClientError, ClientTimeout
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ACCESS_TOKEN, CONF_DEVICE_ID, CONF_HOST, DOMAIN
from .options_flow import CompanionLinkOptionsFlow

_LOGGER = logging.getLogger(__name__)


class CompanionLinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2
    STEP_USER_DATA_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_HOST): str,
            vol.Required("pairing_code"): str,
        }
    )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CompanionLinkOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            code = user_input["pairing_code"].strip().upper()
            try:
                host = str(ipaddress.ip_address(host))
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            if not code:
                errors["pairing_code"] = "invalid_pairing_code"
            if not errors:
                try:
                    session = async_get_clientsession(self.hass)
                    async with session.post(
                        f"http://{host}:8765/api/pair",
                        json={"pairing_code": code},
                        timeout=ClientTimeout(total=10),
                    ) as response:
                        if response.status == 401:
                            errors["pairing_code"] = "invalid_pairing_code"
                        elif response.status != 200:
                            errors["base"] = "cannot_connect"
                        else:
                            paired = await response.json()
                            device_id = paired.get("device_id")
                            access_token = paired.get("access_token")
                            if not device_id or not access_token:
                                errors["base"] = "cannot_connect"
                            else:
                                await self.async_set_unique_id(device_id)
                                entry = next((item for item in self._async_current_entries()
                                              if item.unique_id == device_id), None)
                                entry_data = {
                                    CONF_DEVICE_ID: device_id,
                                    CONF_HOST: host,
                                    CONF_ACCESS_TOKEN: access_token,
                                }
                                if entry is not None:
                                    self.hass.config_entries.async_update_entry(entry, data=entry_data)
                                    await self.hass.config_entries.async_reload(entry.entry_id)
                                    return self.async_abort(reason="reconfigure_successful")
                                return self.async_create_entry(
                                    title=f"Companion Link · {paired.get('device_name', device_id[-6:])}",
                                    data=entry_data,
                                )
                except (asyncio.TimeoutError, ClientError, OSError, ValueError):
                    _LOGGER.debug("Companion Link pairing request failed", exc_info=True)
                    errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="user", data_schema=self.STEP_USER_DATA_SCHEMA, errors=errors)
