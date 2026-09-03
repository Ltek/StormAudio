import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_SCAN_INTERVAL

from .const import DOMAIN


class StormAudioOptionsFlow(config_entries.OptionsFlow):
    """Handle StormAudio options."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, 5),
                ): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
