"""StormAudio sensors - surround mode, StormXT, and video info."""

from __future__ import annotations

import re

from .stormaudio_telnet.constants import SurroundMode
from .stormaudio_telnet.telnet_client import DeviceState

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import helpers
from .const import DOMAIN
from .coordinator import StormAudioCoordinator

_SURROUND_MODE_NAMES = {
    SurroundMode.NATIVE.value: "Native",
    SurroundMode.STEREO_DOWNMIX.value: "Stereo Downmix",
    SurroundMode.DOLBY_SURROUND.value: "Dolby Surround",
    SurroundMode.DTS_NEURAL_X.value: "DTS Neural:X",
    SurroundMode.AURO_MATIC.value: "Auro-Matic",
}

_TIMING_RE = re.compile(r"^(\d+x\d+)@(\d+(?:\.\d+)?Hz)$", re.IGNORECASE)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup config entry."""
    coordinator: StormAudioCoordinator = hass.data[DOMAIN][config.entry_id][
        "coordinator"
    ]

    await helpers.async_wait_2_seconds_for_initial_device_state_or_raise_platform_not_ready(
        coordinator
    )

    device_info = coordinator.data["device_info"]
    device_unique_id = coordinator.data["device_unique_id"]
    device_name = coordinator.data["device_name"]

    add_entities(
        [
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_surround_mode",
                f"{device_name} Surround Mode",
                device_info,
                "mdi:surround-sound",
                _get_surround_mode_name,
                _get_surround_mode_attrs,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_stormxt",
                f"{device_name} StormXT",
                device_info,
                "mdi:surround-sound",
                _get_stormxt_state,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_video_resolution",
                f"{device_name} Video Resolution",
                device_info,
                "mdi:television",
                lambda ds: _split_timing(ds.hdmi1_video_timing)[0],
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_video_encoding",
                f"{device_name} Video Encoding",
                device_info,
                "mdi:hdr",
                lambda ds: ds.hdmi1_hdr,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_video_refresh_rate",
                f"{device_name} Video Refresh Rate",
                device_info,
                "mdi:television-ambient-light",
                lambda ds: _split_timing(ds.hdmi1_video_timing)[1],
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_active_speaker",
                f"{device_name} Active Speaker Config",
                device_info,
                "mdi:speaker-multiple",
                lambda ds: ds.active_speaker_id,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_sample_rate",
                f"{device_name} Sample Rate",
                device_info,
                "mdi:sine-wave",
                lambda ds: ds.sample_rate,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_stream_type",
                f"{device_name} Stream Type",
                device_info,
                "mdi:waveform",
                lambda ds: ds.stream_type,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_channel_format",
                f"{device_name} Channel Format",
                device_info,
                "mdi:speaker-multiple",
                lambda ds: ds.channel_format,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_video_input",
                f"{device_name} Video Input",
                device_info,
                "mdi:hdmi-port",
                lambda ds: ds.hdmi1_video_input,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_video_sync",
                f"{device_name} Video Sync",
                device_info,
                "mdi:sync",
                lambda ds: ds.hdmi1_sync,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_video_copy_protection",
                f"{device_name} Video Copy Protection",
                device_info,
                "mdi:shield-lock",
                lambda ds: ds.hdmi1_cp,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_video_colorspace",
                f"{device_name} Video Color Space",
                device_info,
                "mdi:palette",
                lambda ds: ds.hdmi1_colorspace,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_video_colordepth",
                f"{device_name} Video Color Depth",
                device_info,
                "mdi:palette-outline",
                lambda ds: ds.hdmi1_colordepth,
            ),
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_video_mode",
                f"{device_name} Video Mode",
                device_info,
                "mdi:television-guide",
                lambda ds: ds.hdmi1_mode,
            ),
        ]
    )


def _get_surround_mode_name(device_state: DeviceState) -> str | None:
    if device_state.surround_mode_id is None:
        return None
    return _SURROUND_MODE_NAMES.get(
        device_state.surround_mode_id, str(device_state.surround_mode_id)
    )


def _get_surround_mode_attrs(device_state: DeviceState) -> dict:
    """Per API doc section 3.3.3: the selected surround mode is only
    actually engaged if it matches ssp.allowedmode; otherwise the
    processor is really running a different mode (e.g. you selected
    Auro-Matic but the incoming content can't be upmixed to it)."""
    engaged = None
    if (
        device_state.surround_mode_id is not None
        and device_state.allowed_mode_id is not None
    ):
        engaged = device_state.surround_mode_id == device_state.allowed_mode_id
    return {"engaged": engaged}


def _get_stormxt_state(device_state: DeviceState) -> str | None:
    value = device_state.stormxt
    if value is None:
        return None
    if value == "error":
        return "unavailable"
    return "on" if value else "off"


def _split_timing(timing: str | None) -> tuple[str | None, str | None]:
    """Split '1920x1080@60Hz' into ('1920x1080', '60Hz')."""
    if not timing:
        return (None, None)
    match = _TIMING_RE.match(timing.strip())
    if not match:
        return (timing, None)
    return (match.group(1), match.group(2))


class StormAudioSensor(CoordinatorEntity, SensorEntity):
    """StormAudio read-only sensor."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
        icon: str,
        get_value_fn,
        get_extra_attrs_fn=None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_unique_id = unique_id
        self._attr_icon = icon
        self._attr_name = name
        self._attr_device_info = parent_device_info
        self._get_value_fn = get_value_fn
        self._get_extra_attrs_fn = get_extra_attrs_fn

        self._set_state_from_device()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_state_from_device()
        self.async_write_ha_state()

    def _set_state_from_device(self):
        device_state: DeviceState = self.coordinator.data["device_state"]
        self._attr_available = self.coordinator.connected

        if device_state is not None:
            self._attr_native_value = self._get_value_fn(device_state)
            if self._get_extra_attrs_fn is not None:
                self._attr_extra_state_attributes = self._get_extra_attrs_fn(
                    device_state
                )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        available: bool = self._attr_available
        if available:
            available = super().available
        return available
