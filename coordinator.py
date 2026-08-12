"""StormAudio data update coordinator."""

from __future__ import annotations

import asyncio
from decimal import Decimal
import logging

from .stormaudio_telnet.constants import PowerCommand
from .stormaudio_telnet.telnet_client import DeviceState, TelnetClient
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger("stormaudio")

# Validation of user configuration
MEDIA_PLAYER_PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME): cv.string, vol.Required(CONF_HOST): cv.string}
)


class StormAudioCoordinator(DataUpdateCoordinator):
    """StormAudio data update coordinator."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="StormAudio",
        )
        self._host: str = host
        self._telnet_client: TelnetClient = TelnetClient(
            self._host,
            async_on_device_state_updated=self._async_on_device_state_updated,
            async_on_disconnected=self._async_on_disconnected,
            async_on_raw_line_received=self._async_on_raw_line_received,
        )
        self._connected: bool = False
        self._should_reconnect: bool = False
        self._connection_task: asyncio.Task = None

    @property
    def connected(self) -> bool:
        """Gets a value indicating whether the underlying connection is established."""
        return self._connected

    def connect_and_stay_connected(self) -> None:
        """Connect to the StormAudio device; if the connection is dropped, reconnect indefinitely."""
        self._should_reconnect = True
        self._connection_task = asyncio.create_task(self._async_connect())

    async def _async_connect(self):
        while True:
            try:
                await self._telnet_client.async_connect()
                self._connected = True
                await self._telnet_client.async_request_triggers()
                await self._async_on_device_state_updated()
                break
            except ConnectionError:
                if not self._should_reconnect:
                    break
                await asyncio.sleep(2)

    async def _async_on_raw_line_received(self, line: str) -> None:
        """Debug hook - logs every raw line from the StormAudio device. Enable debug
        logging for this integration to see traffic, e.g. for diagnosing
        unexpected disconnects or misparsed values."""
        _LOGGER.debug("StormAudio device raw line: %s", line)


    async def _async_on_disconnected(self) -> None:
        self._connected = False
        await self._async_on_device_state_updated()
        if self._should_reconnect:
            self.connect_and_stay_connected()

    async def async_disconnect(self) -> None:
        """Disconnect from the StormAudio device."""
        self._should_reconnect = False
        if self._connection_task is not None:
            await self._connection_task
        await self._telnet_client.async_disconnect()

    async def _async_on_device_state_updated(self) -> None:
        device_state: DeviceState = self._telnet_client.get_device_state()
        device_unique_id: str = self.config_entry.unique_id
        device_name: str = self.config_entry.title
        device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            manufacturer=device_state.brand,
            model=device_state.model,
            name=device_name,
        )
        data = {
            "device_state": device_state,
            "device_unique_id": device_unique_id,
            "device_name": device_name,
            "device_info": device_info,
        }
        self.async_set_updated_data(data)

    async def async_set_power_state(self, power_command: PowerCommand):
        """Set power state (on/off)."""
        await self._telnet_client.async_set_power_command(power_command)

    async def async_set_input_id(self, input_id: int):
        """Set input ID."""
        await self._telnet_client.async_set_input_id(input_id)

    async def async_set_input_zone2_id(self, input_zone2_id: int):
        """Set input Zone2 ID."""
        await self._telnet_client.async_set_input_zone2_id(input_zone2_id)

    async def async_set_volume(self, volume_db: Decimal):
        """Set volume in dB (-100..0)."""
        await self._telnet_client.async_set_volume(volume_db)

    async def async_set_mute(self, mute: bool):
        """Set mute (True == muted, False == unmuted)."""
        await self._telnet_client.async_set_mute(mute)

    async def async_toggle_mute(self):
        """Toggle mute."""
        await self._telnet_client.async_toggle_mute()

    async def async_set_preset_id(self, preset_id: int):
        """Set preset ID."""
        await self._telnet_client.async_set_preset_id(preset_id)

    async def async_set_surround_mode_id(self, surround_mode_id: int):
        """Set preferred surround mode (see constants.SurroundMode)."""
        await self._telnet_client.async_set_surround_mode_id(surround_mode_id)

    async def async_set_stormxt(self, on: bool):
        """Set StormXT on/off."""
        await self._telnet_client.async_set_stormxt(on)

    async def async_toggle_stormxt(self):
        """Toggle StormXT."""
        await self._telnet_client.async_toggle_stormxt()

    async def async_set_bass(self, bass_db: int):
        """Set bass tone control, -6..6 dB."""
        await self._telnet_client.async_set_bass(bass_db)

    async def async_set_treble(self, treble_db: int):
        """Set treble tone control, -6..6 dB."""
        await self._telnet_client.async_set_treble(treble_db)

    async def async_set_brightness(self, brightness_db: int):
        """Set brightness control, -6..6 dB."""
        await self._telnet_client.async_set_brightness(brightness_db)

    async def async_set_center_enhance(self, center_enhance_db: int):
        """Set center enhance control, -6..6 dB."""
        await self._telnet_client.async_set_center_enhance(center_enhance_db)

    async def async_set_surround_enhance(self, surround_enhance_db: int):
        """Set surround enhance control, -6..6 dB."""
        await self._telnet_client.async_set_surround_enhance(surround_enhance_db)

    async def async_set_lfe_enhance(self, lfe_enhance_db: int):
        """Set LFE enhance control, -6..6 dB."""
        await self._telnet_client.async_set_lfe_enhance(lfe_enhance_db)

    async def async_set_lipsync(self, lipsync_ms: int):
        """Set lip sync delay in ms."""
        await self._telnet_client.async_set_lipsync(lipsync_ms)

    # --- Additional theater controls ---

    async def async_set_dim(self, on: bool):
        await self._telnet_client.async_set_dim(on)

    async def async_toggle_dim(self):
        await self._telnet_client.async_toggle_dim()

    async def async_set_loudness(self, level: int):
        await self._telnet_client.async_set_loudness(level)

    async def async_set_drc(self, mode: str):
        await self._telnet_client.async_set_drc(mode)

    async def async_set_dolby_mode(self, mode: int):
        await self._telnet_client.async_set_dolby_mode(mode)

    async def async_set_dolby_virtualizer(self, on: bool):
        await self._telnet_client.async_set_dolby_virtualizer(on)

    async def async_toggle_dolby_virtualizer(self):
        await self._telnet_client.async_toggle_dolby_virtualizer()

    async def async_set_imax_mode(self, mode: str):
        await self._telnet_client.async_set_imax_mode(mode)

    async def async_set_dialog_control(self, dialog_control_db: int):
        await self._telnet_client.async_set_dialog_control(dialog_control_db)

    async def async_set_dialog_norm(self, on: bool):
        await self._telnet_client.async_set_dialog_norm(on)

    async def async_toggle_dialog_norm(self):
        await self._telnet_client.async_toggle_dialog_norm()

    async def async_set_center_spread(self, on: bool):
        await self._telnet_client.async_set_center_spread(on)

    async def async_toggle_center_spread(self):
        await self._telnet_client.async_toggle_center_spread()

    async def async_set_auro_strength(self, strength: int):
        await self._telnet_client.async_set_auro_strength(strength)

    async def async_set_auro_preset(self, preset_id: int):
        await self._telnet_client.async_set_auro_preset(preset_id)

    async def async_set_sphereaudio_effect(self, effect_id: int):
        await self._telnet_client.async_set_sphereaudio_effect(effect_id)

    async def async_set_lfe_dim(self, on: bool):
        await self._telnet_client.async_set_lfe_dim(on)

    async def async_toggle_lfe_dim(self):
        await self._telnet_client.async_toggle_lfe_dim()

    # --- Front panel ---

    async def async_set_frontpanel_color(self, color: str):
        await self._telnet_client.async_set_frontpanel_color(color)

    async def async_set_frontpanel_stbybright(self, brightness: int):
        await self._telnet_client.async_set_frontpanel_stbybright(brightness)

    async def async_set_frontpanel_actbright(self, brightness: int):
        await self._telnet_client.async_set_frontpanel_actbright(brightness)

    async def async_set_frontpanel_stbytime(self, seconds: int):
        await self._telnet_client.async_set_frontpanel_stbytime(seconds)

    # --- Triggers ---

    async def async_set_trigger(self, trigger_num: int, on: bool):
        await self._telnet_client.async_set_trigger(trigger_num, on)

    async def async_toggle_trigger(self, trigger_num: int):
        await self._telnet_client.async_toggle_trigger(trigger_num)

    # --- Zones ---

    async def async_set_zone_volume(self, zone_id: int, volume_db: Decimal):
        await self._telnet_client.async_set_zone_volume(zone_id, volume_db)

    async def async_set_zone_mute(self, zone_id: int, mute: bool):
        await self._telnet_client.async_set_zone_mute(zone_id, mute)

    async def async_toggle_zone_mute(self, zone_id: int):
        await self._telnet_client.async_toggle_zone_mute(zone_id)

    async def async_set_zone_bass(self, zone_id: int, bass_db: int):
        await self._telnet_client.async_set_zone_bass(zone_id, bass_db)

    async def async_set_zone_treble(self, zone_id: int, treble_db: int):
        await self._telnet_client.async_set_zone_treble(zone_id, treble_db)

    async def async_set_zone_lipsync(self, zone_id: int, lipsync_ms: int):
        await self._telnet_client.async_set_zone_lipsync(zone_id, lipsync_ms)

    async def async_set_zone_eq(self, zone_id: int, eq_on: bool):
        await self._telnet_client.async_set_zone_eq(zone_id, eq_on)

    async def async_toggle_zone_eq(self, zone_id: int):
        await self._telnet_client.async_toggle_zone_eq(zone_id)

    async def async_set_zone_binaural_mode(self, zone_id: int, binaural: bool):
        await self._telnet_client.async_set_zone_binaural_mode(zone_id, binaural)

    async def async_toggle_zone_binaural_mode(self, zone_id: int):
        await self._telnet_client.async_toggle_zone_binaural_mode(zone_id)

    async def async_set_zone_loudness(self, zone_id: int, level: int):
        await self._telnet_client.async_set_zone_loudness(zone_id, level)
