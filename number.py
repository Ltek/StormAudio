"""StormAudio numbers."""

from __future__ import annotations

from decimal import Decimal

from .stormaudio_telnet.telnet_client import DeviceState, ProcessorState

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import helpers
from .const import DOMAIN
from .coordinator import StormAudioCoordinator

# Per API doc sections 3.4.5-3.4.12: documented range for these trim
# controls is -6..6 dB, step 1. The unit's installer-configured "Audio
# Control Range MAX" setting may clamp this further; out-of-range writes
# are simply clamped/ignored by the StormAudio device, so this is a safe outer bound.
TRIM_DB_MIN = -6
TRIM_DB_MAX = 6

# Lip sync: doc says "-(Inputs AV Delay + Settings AV Zone Delay) to
# 100ms" - the true minimum depends on your configured delay settings, so
# a broad range is used here and the StormAudio device will clamp to whatever's actually
# allowed.
LIPSYNC_MS_MIN = -100
LIPSYNC_MS_MAX = 100

AURO_STRENGTH_MIN = 0
AURO_STRENGTH_MAX = 15

DIALOG_CONTROL_DB_MIN = 0
DIALOG_CONTROL_DB_MAX = 6

FRONTPANEL_BRIGHTNESS_MIN = 0
FRONTPANEL_BRIGHTNESS_MAX = 100
FRONTPANEL_BRIGHTNESS_STEP = 10

# Zone volume is on the same -0..-100dB scale as the main volume
ZONE_VOLUME_PERCENT_MIN = 0.0
ZONE_VOLUME_PERCENT_MAX = 100.0


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
            StormAudioVolumeNumber(
                coordinator,
                f"{device_unique_id}_volume_level",
                f"{device_name} Volume Level",
                device_info,
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_center_enhance",
                f"{device_name} Center Enhance",
                device_info,
                "mdi:tune-vertical",
                TRIM_DB_MIN,
                TRIM_DB_MAX,
                "dB",
                lambda device_state: device_state.center_enhance_db,
                lambda coordinator, value: coordinator.async_set_center_enhance(
                    value
                ),
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_surround_enhance",
                f"{device_name} Surround Enhance",
                device_info,
                "mdi:tune-vertical",
                TRIM_DB_MIN,
                TRIM_DB_MAX,
                "dB",
                lambda device_state: device_state.surround_enhance_db,
                lambda coordinator, value: coordinator.async_set_surround_enhance(
                    value
                ),
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_lfe_enhance",
                f"{device_name} LFE Enhance",
                device_info,
                "mdi:tune-vertical",
                TRIM_DB_MIN,
                TRIM_DB_MAX,
                "dB",
                lambda device_state: device_state.lfe_enhance_db,
                lambda coordinator, value: coordinator.async_set_lfe_enhance(value),
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_bass",
                f"{device_name} Bass",
                device_info,
                "mdi:music-clef-bass",
                TRIM_DB_MIN,
                TRIM_DB_MAX,
                "dB",
                lambda device_state: device_state.bass_db,
                lambda coordinator, value: coordinator.async_set_bass(value),
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_treble",
                f"{device_name} Treble",
                device_info,
                "mdi:music-clef-treble",
                TRIM_DB_MIN,
                TRIM_DB_MAX,
                "dB",
                lambda device_state: device_state.treble_db,
                lambda coordinator, value: coordinator.async_set_treble(value),
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_brightness",
                f"{device_name} Brightness",
                device_info,
                "mdi:brightness-6",
                TRIM_DB_MIN,
                TRIM_DB_MAX,
                "dB",
                lambda device_state: device_state.brightness_db,
                lambda coordinator, value: coordinator.async_set_brightness(value),
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_lipsync",
                f"{device_name} LipSync",
                device_info,
                "mdi:sync",
                LIPSYNC_MS_MIN,
                LIPSYNC_MS_MAX,
                "ms",
                lambda device_state: device_state.lipsync_ms,
                lambda coordinator, value: coordinator.async_set_lipsync(value),
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_auro_strength",
                f"{device_name} Auro Strength",
                device_info,
                "mdi:surround-sound",
                AURO_STRENGTH_MIN,
                AURO_STRENGTH_MAX,
                None,
                lambda device_state: device_state.auro_strength,
                lambda coordinator, value: coordinator.async_set_auro_strength(value),
                enabled_default=False,
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_dialog_control",
                f"{device_name} Dialog Control",
                device_info,
                "mdi:message-text",
                DIALOG_CONTROL_DB_MIN,
                DIALOG_CONTROL_DB_MAX,
                "dB",
                lambda device_state: device_state.dialog_control_db,
                lambda coordinator, value: coordinator.async_set_dialog_control(
                    value
                ),
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_frontpanel_standby_brightness",
                f"{device_name} Front Panel Standby Brightness",
                device_info,
                "mdi:brightness-4",
                FRONTPANEL_BRIGHTNESS_MIN,
                FRONTPANEL_BRIGHTNESS_MAX,
                "%",
                lambda device_state: device_state.frontpanel_stbybright,
                lambda coordinator, value: coordinator.async_set_frontpanel_stbybright(
                    value
                ),
                step=FRONTPANEL_BRIGHTNESS_STEP,
                enabled_default=False,
            ),
            StormAudioTrimNumber(
                coordinator,
                f"{device_unique_id}_frontpanel_active_brightness",
                f"{device_name} Front Panel Active Brightness",
                device_info,
                "mdi:brightness-7",
                FRONTPANEL_BRIGHTNESS_MIN,
                FRONTPANEL_BRIGHTNESS_MAX,
                "%",
                lambda device_state: device_state.frontpanel_actbright,
                lambda coordinator, value: coordinator.async_set_frontpanel_actbright(
                    value
                ),
                step=FRONTPANEL_BRIGHTNESS_STEP,
                enabled_default=False,
            ),
        ]
    )

    # --- Per-zone number entities ---
    # Zones are only known once the StormAudio device has sent its zones.list broadcast,
    # which normally arrives during the initial value burst covered by the
    # helper wait above (same as inputs/presets).
    device_state = coordinator.data["device_state"]
    zones = device_state.zones if device_state is not None else None
    if zones:
        zone_entities = []
        for zone in zones:
            zone_entities.extend(
                [
                    StormAudioZoneVolumeNumber(
                        coordinator,
                        f"{device_unique_id}_zone{zone.id}_volume",
                        f"{device_name} {zone.name} Volume",
                        device_info,
                        zone.id,
                    ),
                    StormAudioZoneTrimNumber(
                        coordinator,
                        f"{device_unique_id}_zone{zone.id}_bass",
                        f"{device_name} {zone.name} Bass",
                        device_info,
                        "mdi:music-clef-bass",
                        TRIM_DB_MIN,
                        TRIM_DB_MAX,
                        "dB",
                        zone.id,
                        lambda z: z.bass_db,
                        lambda coordinator, zone_id, value: coordinator.async_set_zone_bass(
                            zone_id, value
                        ),
                    ),
                    StormAudioZoneTrimNumber(
                        coordinator,
                        f"{device_unique_id}_zone{zone.id}_treble",
                        f"{device_name} {zone.name} Treble",
                        device_info,
                        "mdi:music-clef-treble",
                        TRIM_DB_MIN,
                        TRIM_DB_MAX,
                        "dB",
                        zone.id,
                        lambda z: z.treble_db,
                        lambda coordinator, zone_id, value: coordinator.async_set_zone_treble(
                            zone_id, value
                        ),
                    ),
                    StormAudioZoneTrimNumber(
                        coordinator,
                        f"{device_unique_id}_zone{zone.id}_lipsync",
                        f"{device_name} {zone.name} LipSync",
                        device_info,
                        "mdi:sync",
                        LIPSYNC_MS_MIN,
                        LIPSYNC_MS_MAX,
                        "ms",
                        zone.id,
                        lambda z: z.lipsync_ms,
                        lambda coordinator, zone_id, value: coordinator.async_set_zone_lipsync(
                            zone_id, value
                        ),
                    ),
                ]
            )
        add_entities(zone_entities)


class StormAudioVolumeNumber(CoordinatorEntity, NumberEntity):
    """StormAudio volume number/control."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 1.0
        self._attr_native_value = None

        self._attr_unique_id = unique_id
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:volume-high"
        self._attr_name = name

        self._attr_device_info = parent_device_info

        self._set_state_from_device()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_state_from_device()
        self.async_write_ha_state()

    def _set_state_from_device(self):
        device_state: DeviceState = self.coordinator.data["device_state"]
        self._attr_available = self.coordinator.connected

        if device_state is not None and device_state.volume_db is not None:
            self._attr_available = device_state.processor_state in [
                ProcessorState.ON,
                ProcessorState.INITIALIZING,
            ]

            decimal_volume_db: Decimal = device_state.volume_db
            fraction_value: float = float(
                helpers.decibels_to_volume_level(decimal_volume_db)
            )
            self._attr_native_value = round(fraction_value * 100.0, 0)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        available: bool = self._attr_available
        if available:
            available = super().available
        return available

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if value < 0.0 or value > 100.0:
            return

        fraction_value: Decimal = round(Decimal(value / 100.0), 2)
        decimal_volume_db: Decimal = helpers.volume_level_to_decibels(fraction_value)

        await self.coordinator.async_set_volume(decimal_volume_db)
        self._attr_native_value = value
        self.async_write_ha_state()


class StormAudioTrimNumber(CoordinatorEntity, NumberEntity):
    """StormAudio audio trim control (Bass, Treble, Brightness,
    Center/Surround/LFE Enhance, LipSync)."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
        icon: str,
        min_value: float,
        max_value: float,
        unit: str,
        get_value_fn,
        async_set_value_fn,
        step: float = 1.0,
        enabled_default: bool = True,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = unit

        self._attr_unique_id = unique_id
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = icon
        self._attr_name = name

        self._attr_device_info = parent_device_info
        self._attr_entity_registry_enabled_default = enabled_default
        self._get_value_fn = get_value_fn
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

        value = self._get_value_fn(device_state) if device_state is not None else None
        if value is not None:
            self._attr_available = device_state.processor_state in [
                ProcessorState.ON,
                ProcessorState.INITIALIZING,
            ]
            self._attr_native_value = value

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        available: bool = self._attr_available
        if available:
            available = super().available
        return available

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if value < self._attr_native_min_value or value > self._attr_native_max_value:
            return

        await self._async_set_value_fn(self.coordinator, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()


def _find_zone(device_state: DeviceState, zone_id: int):
    """Look up a zone by ID in the current zones list (a new list of Zone
    objects is built each time zones.list is reparsed, so we can't hold a
    direct reference across updates)."""
    if device_state is None or device_state.zones is None:
        return None
    for zone in device_state.zones:
        if zone.id == zone_id:
            return zone
    return None


class StormAudioZoneVolumeNumber(CoordinatorEntity, NumberEntity):
    """Per-zone volume control (same -0..-100dB scale as main volume)."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
        zone_id: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 1.0
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = "%"

        self._attr_unique_id = unique_id
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = "mdi:volume-high"
        self._attr_name = name

        self._attr_device_info = parent_device_info
        self._attr_entity_registry_enabled_default = False
        self._zone_id = zone_id

        self._set_state_from_device()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_state_from_device()
        self.async_write_ha_state()

    def _set_state_from_device(self):
        device_state: DeviceState = self.coordinator.data["device_state"]
        self._attr_available = self.coordinator.connected

        zone = _find_zone(device_state, self._zone_id)
        if zone is not None and zone.volume_db is not None:
            fraction_value: float = float(
                helpers.decibels_to_volume_level(zone.volume_db)
            )
            self._attr_native_value = round(fraction_value * 100.0, 0)
        else:
            self._attr_available = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        available: bool = self._attr_available
        if available:
            available = super().available
        return available

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if value < 0.0 or value > 100.0:
            return

        fraction_value: Decimal = round(Decimal(value / 100.0), 2)
        decimal_volume_db: Decimal = helpers.volume_level_to_decibels(fraction_value)

        await self.coordinator.async_set_zone_volume(self._zone_id, decimal_volume_db)
        self._attr_native_value = value
        self.async_write_ha_state()


class StormAudioZoneTrimNumber(CoordinatorEntity, NumberEntity):
    """Per-zone trim control (Bass, Treble, LipSync)."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
        icon: str,
        min_value: float,
        max_value: float,
        unit: str,
        zone_id: int,
        get_zone_value_fn,
        async_set_value_fn,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = 1.0
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = unit

        self._attr_unique_id = unique_id
        self._attr_mode = NumberMode.SLIDER
        self._attr_icon = icon
        self._attr_name = name

        self._attr_device_info = parent_device_info
        self._attr_entity_registry_enabled_default = False
        self._zone_id = zone_id
        self._get_zone_value_fn = get_zone_value_fn
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

        zone = _find_zone(device_state, self._zone_id)
        value = self._get_zone_value_fn(zone) if zone is not None else None
        if value is not None:
            self._attr_native_value = value
        else:
            self._attr_available = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        available: bool = self._attr_available
        if available:
            available = super().available
        return available

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if value < self._attr_native_min_value or value > self._attr_native_max_value:
            return

        await self._async_set_value_fn(self.coordinator, self._zone_id, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()
