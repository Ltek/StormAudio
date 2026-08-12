"""StormAudio selects."""

from __future__ import annotations

import itertools

from .stormaudio_telnet.constants import (
    AuroPreset,
    DolbyMode,
    FRONT_PANEL_COLORS,
    FRONT_PANEL_STANDBY_DELAYS,
    LoudnessLevel,
    SphereAudioEffect,
)
from .stormaudio_telnet.telnet_client import DeviceState, ProcessorState

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import helpers
from .const import DOMAIN
from .coordinator import StormAudioCoordinator

DOLBY_MODE_NAMES = {
    DolbyMode.OFF.value: "Off",
    DolbyMode.MOVIE.value: "Movie",
    DolbyMode.MUSIC.value: "Music",
    DolbyMode.NIGHT.value: "Night",
}

AURO_PRESET_NAMES = {
    AuroPreset.SMALL.value: "Small",
    AuroPreset.MEDIUM.value: "Medium",
    AuroPreset.LARGE.value: "Large",
    AuroPreset.SPEECH.value: "Speech",
}

SPHEREAUDIO_EFFECT_NAMES = {
    SphereAudioEffect.BYPASS.value: "Bypass",
    SphereAudioEffect.LOUNGE.value: "Lounge",
    SphereAudioEffect.HOME_CINEMA.value: "Home Cinema",
    SphereAudioEffect.CONCERT.value: "Concert",
    SphereAudioEffect.CINEMA.value: "Cinema",
}

LOUDNESS_NAMES = {
    LoudnessLevel.OFF.value: "Off",
    LoudnessLevel.LOW.value: "Low",
    LoudnessLevel.MEDIUM.value: "Medium",
    LoudnessLevel.FULL.value: "Full",
}

FRONTPANEL_STANDBY_DELAY_NAMES = {
    seconds: f"{seconds}s" for seconds in FRONT_PANEL_STANDBY_DELAYS
}


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
            StormAudioSelect(
                coordinator,
                f"{device_unique_id}_source",
                f"{device_name} Source",
                device_info,
                lambda device_state: (
                    device_state.inputs is not None
                    and device_state.input_id is not None
                ),
                lambda device_state: ((i.id, i.name) for i in device_state.inputs),
                lambda device_state: device_state.input_id,
                lambda coordinator, selected_id: coordinator.async_set_input_id(
                    selected_id
                ),
            ),
            StormAudioSelect(
                coordinator,
                f"{device_unique_id}_source_zone2",
                f"{device_name} Source (Zone 2)",
                device_info,
                lambda device_state: (
                    device_state.inputs is not None
                    and device_state.input_zone2_id is not None
                ),
                lambda device_state: itertools.chain(
                    ((i.id, i.name) for i in device_state.inputs),
                    # add an entry to allow for selection of no-value; maps to ID 0
                    [(0, "")],
                ),
                lambda device_state: device_state.input_zone2_id,
                lambda coordinator, selected_id: coordinator.async_set_input_zone2_id(
                    selected_id
                ),
            ),
            StormAudioSelect(
                coordinator,
                f"{device_unique_id}_preset",
                f"{device_name} Preset",
                device_info,
                lambda device_state: (
                    device_state.presets is not None
                    and device_state.preset_id is not None
                ),
                lambda device_state: ((i.id, i.name) for i in device_state.presets),
                lambda device_state: device_state.preset_id,
                lambda coordinator, selected_id: coordinator.async_set_preset_id(
                    selected_id
                ),
            ),
            StormAudioSelect(
                coordinator,
                f"{device_unique_id}_dolby_mode",
                f"{device_name} Dolby Mode",
                device_info,
                lambda device_state: device_state.dolby_mode is not None,
                lambda device_state: DOLBY_MODE_NAMES.items(),
                lambda device_state: device_state.dolby_mode,
                lambda coordinator, selected_id: coordinator.async_set_dolby_mode(
                    selected_id
                ),
            ),
            StormAudioSelect(
                coordinator,
                f"{device_unique_id}_auro_preset",
                f"{device_name} Auro Preset",
                device_info,
                lambda device_state: device_state.auro_preset is not None,
                lambda device_state: AURO_PRESET_NAMES.items(),
                lambda device_state: device_state.auro_preset,
                lambda coordinator, selected_id: coordinator.async_set_auro_preset(
                    selected_id
                ),
            ),
            StormAudioSelect(
                coordinator,
                f"{device_unique_id}_sphereaudio_effect",
                f"{device_name} SphereAudio Effect",
                device_info,
                lambda device_state: isinstance(
                    device_state.sphereaudio_effect, int
                ),
                lambda device_state: SPHEREAUDIO_EFFECT_NAMES.items(),
                lambda device_state: device_state.sphereaudio_effect,
                lambda coordinator, selected_id: coordinator.async_set_sphereaudio_effect(
                    selected_id
                ),
            ),
            StormAudioSelect(
                coordinator,
                f"{device_unique_id}_loudness",
                f"{device_name} Loudness",
                device_info,
                lambda device_state: device_state.loudness is not None,
                lambda device_state: LOUDNESS_NAMES.items(),
                lambda device_state: device_state.loudness,
                lambda coordinator, selected_id: coordinator.async_set_loudness(
                    selected_id
                ),
            ),
            StormAudioSelect(
                coordinator,
                f"{device_unique_id}_frontpanel_standby_delay",
                f"{device_name} Front Panel Standby Delay",
                device_info,
                lambda device_state: device_state.frontpanel_stbytime is not None,
                lambda device_state: FRONTPANEL_STANDBY_DELAY_NAMES.items(),
                lambda device_state: device_state.frontpanel_stbytime,
                lambda coordinator, selected_id: coordinator.async_set_frontpanel_stbytime(
                    selected_id
                ),
            ),
            StormAudioStringSelect(
                coordinator,
                f"{device_unique_id}_drc",
                f"{device_name} DRC",
                device_info,
                ["on", "off", "auto"],
                lambda device_state: device_state.drc,
                lambda coordinator, selected: coordinator.async_set_drc(selected),
            ),
            StormAudioStringSelect(
                coordinator,
                f"{device_unique_id}_imax_mode",
                f"{device_name} IMAX Mode",
                device_info,
                ["on", "off", "auto"],
                lambda device_state: device_state.imax_mode,
                lambda coordinator, selected: coordinator.async_set_imax_mode(
                    selected
                ),
            ),
            StormAudioStringSelect(
                coordinator,
                f"{device_unique_id}_frontpanel_color",
                f"{device_name} Front Panel Color",
                device_info,
                FRONT_PANEL_COLORS,
                lambda device_state: device_state.frontpanel_color,
                lambda coordinator, selected: coordinator.async_set_frontpanel_color(
                    selected
                ),
            ),
        ]
    )


class StormAudioSelect(CoordinatorEntity, SelectEntity):
    """StormAudio select."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
        is_data_available_fn,
        get_id_name_map_fn,
        get_current_id_fn,
        async_set_current_id_fn,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_options = None
        self._attr_current_option = None

        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:audio-video"
        self._attr_name = name

        self._attr_device_info = parent_device_info
        self._is_data_available_fn = is_data_available_fn
        self._get_id_name_map_fn = get_id_name_map_fn
        self._get_current_id_fn = get_current_id_fn
        self._async_set_current_id_fn = async_set_current_id_fn

        self._set_state_from_device()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_state_from_device()
        self.async_write_ha_state()

    def _set_state_from_device(self):
        device_state: DeviceState = self.coordinator.data["device_state"]
        self._attr_available = self.coordinator.connected

        if device_state is not None and self._is_data_available_fn(device_state):
            self._attr_available = device_state.processor_state in [
                ProcessorState.ON,
                ProcessorState.INITIALIZING,
            ]

            id_name_map = self._get_id_name_map_fn(device_state)
            self._id_to_name = dict(id_name_map)
            self._name_to_id = {v: k for k, v in self._id_to_name.items()}
            self._attr_options = list(self._name_to_id.keys())

            self._attr_current_option = None
            current_id = self._get_current_id_fn(device_state)
            if self._id_to_name is not None and current_id in self._id_to_name:
                self._attr_current_option = self._id_to_name[current_id]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        available: bool = self._attr_available
        if available:
            available = super().available
        return available

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if self._name_to_id is None:
            return

        option_id: int
        if option not in self._name_to_id:
            option_id = 0
        else:
            option_id = self._name_to_id[option]

        await self._async_set_current_id_fn(self.coordinator, option_id)
        self._attr_current_option = option
        self.async_write_ha_state()


class StormAudioStringSelect(CoordinatorEntity, SelectEntity):
    """StormAudio select backed by a plain string value rather than an
    ID/name map (DRC, IMAX Mode, Front Panel Color)."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
        options: list[str],
        get_current_value_fn,
        async_set_value_fn,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_options = options
        self._attr_current_option = None

        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:tune"
        self._attr_name = name

        self._attr_device_info = parent_device_info
        self._get_current_value_fn = get_current_value_fn
        self._async_set_value_fn = async_set_value_fn

        self._set_state_from_device()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_state_from_device()
        self.async_write_ha_state()

    def _set_state_from_device(self):
        device_state: DeviceState = self.coordinator.data["device_state"]
        self._attr_available = self.coordinator.connected

        current = (
            self._get_current_value_fn(device_state)
            if device_state is not None
            else None
        )
        if current is not None:
            self._attr_available = device_state.processor_state in [
                ProcessorState.ON,
                ProcessorState.INITIALIZING,
            ]
            self._attr_current_option = current
        else:
            self._attr_available = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        available: bool = self._attr_available
        if available:
            available = super().available
        return available

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._async_set_value_fn(self.coordinator, option)
        self._attr_current_option = option
        self.async_write_ha_state()
