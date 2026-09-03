"""StormAudio sensors - surround mode, StormXT, and video info."""

from __future__ import annotations

import re

from .stormaudio_telnet.constants import HDMI_OUTPUT_IDS, SurroundMode
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

    entities = [
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
    ]

    # Per-output HDMI video sensors. One set is created for every output in
    # HDMI_OUTPUT_IDS so a user whose display is on HDMI OUT 2 (or who runs
    # dual displays) can read video info from any output. To keep the OUT 1
    # entities backwards-compatible, output 1 keeps its original unique_ids
    # and names and its original enabled-by-default behavior; every other
    # output's sensors are disabled by default, so they only appear once the
    # user opts in from the entity settings.
    for output_id in HDMI_OUTPUT_IDS:
        entities.extend(
            _build_video_sensors(
                coordinator, device_unique_id, device_name, device_info, output_id
            )
        )

    add_entities(entities)


# (key suffix, name suffix, icon, hdmi field extractor, enabled-by-default on
# HDMI OUT 1). The extractor takes the DeviceState and the output id.
_VIDEO_SENSOR_SPECS = [
    (
        "video_resolution",
        "Video Resolution",
        "mdi:television",
        lambda ds, out: _split_timing(ds.get_hdmi_field(out, "timing"))[0],
        True,
    ),
    (
        "video_encoding",
        "Video Encoding",
        "mdi:hdr",
        lambda ds, out: ds.get_hdmi_field(out, "hdr"),
        True,
    ),
    (
        "video_refresh_rate",
        "Video Refresh Rate",
        "mdi:television-ambient-light",
        lambda ds, out: _split_timing(ds.get_hdmi_field(out, "timing"))[1],
        True,
    ),
    (
        "video_input",
        "Video Input",
        "mdi:hdmi-port",
        lambda ds, out: ds.get_hdmi_field(out, "input"),
        False,
    ),
    (
        "video_sync",
        "Video Sync",
        "mdi:sync",
        lambda ds, out: ds.get_hdmi_field(out, "sync"),
        False,
    ),
    (
        "video_copy_protection",
        "Video Copy Protection",
        "mdi:shield-lock",
        lambda ds, out: ds.get_hdmi_field(out, "cp"),
        False,
    ),
    (
        "video_colorspace",
        "Video Color Space",
        "mdi:palette",
        lambda ds, out: ds.get_hdmi_field(out, "colorspace"),
        True,
    ),
    (
        "video_colordepth",
        "Video Color Depth",
        "mdi:palette-outline",
        lambda ds, out: ds.get_hdmi_field(out, "colordepth"),
        True,
    ),
    (
        "video_mode",
        "Video Mode",
        "mdi:television-guide",
        lambda ds, out: ds.get_hdmi_field(out, "mode"),
        False,
    ),
]


def _build_video_sensors(
    coordinator, device_unique_id, device_name, device_info, output_id
) -> list["StormAudioSensor"]:
    """Build the video-info sensors for a single HDMI output."""
    # OUT 1 keeps the original unique_id/name (no suffix) so upgrading
    # installs don't get a second set of "unknown" entities; higher outputs
    # get an "_hdmiN" unique_id suffix and an "HDMI OUT N" label, and are
    # disabled by default.
    is_primary = output_id == HDMI_OUTPUT_IDS[0]
    id_suffix = "" if is_primary else f"_hdmi{output_id}"
    name_suffix = "" if is_primary else f" (HDMI OUT {output_id})"

    sensors = []
    for key, name, icon, extractor, enabled_on_primary in _VIDEO_SENSOR_SPECS:
        sensors.append(
            StormAudioSensor(
                coordinator,
                f"{device_unique_id}_{key}{id_suffix}",
                f"{device_name} {name}{name_suffix}",
                device_info,
                icon,
                (lambda ex, out: lambda ds: ex(ds, out))(extractor, output_id),
                enabled_default=enabled_on_primary if is_primary else False,
            )
        )
    return sensors


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
        enabled_default: bool = True,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_unique_id = unique_id
        self._attr_icon = icon
        self._attr_name = name
        self._attr_device_info = parent_device_info
        self._attr_entity_registry_enabled_default = enabled_default
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
