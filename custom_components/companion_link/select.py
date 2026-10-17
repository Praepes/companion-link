from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import CompanionLinkEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    added = False

    def add_when_supported():
        nonlocal added
        supported = (data.values.get("input_source_supported", False)
                     or data.values.get("input_source_control_available", False)
                     or "G1109" in str(data.values.get("device_model", "")))
        if not added and supported:
            added = True
            async_add_entities([CompanionLinkInputSource(data)])

    entry.async_on_unload(data.add_listener(add_when_supported))
    add_when_supported()


class CompanionLinkInputSource(CompanionLinkEntity, SelectEntity):
    _attr_options = ["Android", "HDMI"]

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "input_source", "投影输入", "mdi:video-input-hdmi")

    @property
    def current_option(self):
        source = self.coordinator.values.get("input_source")
        return source if source in self.options else None

    @property
    def available(self):
        return super().available and bool(
            self.coordinator.values.get("input_source_control_available", False)
        )

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise HomeAssistantError("Unsupported projector input")
        if option == "HDMI" and self.coordinator.values.get("hdmi_connected") is False:
            raise HomeAssistantError("HDMI input cable is not connected")
        result = await self.coordinator._async_send_command("input_source", {"source": option})
        if not result.get("success", False):
            raise HomeAssistantError(result.get("message", "Input switch failed"))
