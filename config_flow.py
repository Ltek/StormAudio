import asyncio
import hashlib
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN
from .options_flow import StormAudioOptionsFlow
from .stormaudio_telnet.telnet_client import TelnetClient

_LOGGER = logging.getLogger(__name__)


def generate_unique_id(host_input: str) -> str:
    """Generate deterministic SHA‑1 based Unique ID from user input."""
    normalized = host_input.lower().strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


async def _async_validate_connection(host: str) -> str | None:
    """Attempt to connect to the given host and wait for initial state.

    Returns an error code string on failure, or None on success.
    """
    async def _async_on_device_state_updated():
        pass

    async def _async_on_disconnected():
        pass

    telnet_client = TelnetClient(
        host,
        async_on_device_state_updated=_async_on_device_state_updated,
        async_on_disconnected=_async_on_disconnected,
    )

    try:
        await telnet_client.async_connect()
    except Exception as err:
        _LOGGER.error("StormAudio connection failed during connect: %s", err)
        return "cannot_connect"

    try:
        for _ in range(40):  # 10 seconds total
            try:
                state = telnet_client.get_device_state()
            except Exception as err:
                _LOGGER.error("StormAudio state read failed: %s", err)
                return "cannot_connect"

            if state is not None and getattr(state, "processor_state", None) is not None:
                return None

            await asyncio.sleep(0.25)
        return "cannot_connect"
    finally:
        await telnet_client.async_disconnect()


class StormAudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """StormAudio configuration flow."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return StormAudioOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_NAME): str,
            }
        )

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]

            error = await _async_validate_connection(host)
            if error is not None:
                errors["base"] = error
                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors=errors,
                )

            # SUCCESS — create entry
            unique_id = generate_unique_id(host)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data={
                    CONF_HOST: host,
                    CONF_NAME: name,
                    "unique_id": unique_id,
                },
            )

        # INITIAL FORM
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Allow the user to change the host/name of an existing entry."""
        errors = {}
        reconfigure_entry = self._get_reconfigure_entry()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=reconfigure_entry.data.get(CONF_HOST)
                ): str,
                vol.Required(
                    CONF_NAME, default=reconfigure_entry.data.get(CONF_NAME)
                ): str,
            }
        )

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input[CONF_NAME]

            new_unique_id = generate_unique_id(host)
            if new_unique_id != reconfigure_entry.unique_id:
                return self.async_abort(reason="unique_id_mismatch")

            error = await _async_validate_connection(host)
            if error is not None:
                errors["base"] = error
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=data_schema,
                    errors=errors,
                )

            return self.async_update_reload_and_abort(
                reconfigure_entry,
                title=name,
                data={
                    **reconfigure_entry.data,
                    CONF_HOST: host,
                    CONF_NAME: name,
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )
