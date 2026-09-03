"""StormAudio switches."""

from __future__ import annotations

from .stormaudio_telnet.constants import PowerCommand
from .stormaudio_telnet.telnet_client import DeviceState, ProcessorState

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import helpers
from .const import DOMAIN
from .coordinator import StormAudioCoordinator


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
            StormAudioMuteSwitch(
                coordinator,
                f"{device_unique_id}_mute",
                f"{device_name} Mute",
                device_info,
            ),
            StormAudioPowerSwitch(
                coordinator,
                f"{device_unique_id}_power",
                f"{device_name} Power",
                device_info,
            ),
            StormAudioToggleSwitch(
                coordinator,
                f"{device_unique_id}_dim",
                f"{device_name} Dim",
                device_info,
                "mdi:brightness-6",
                lambda device_state: device_state.dim,
                lambda coordinator: coordinator.async_set_dim(True),
                lambda coordinator: coordinator.async_set_dim(False),
            ),
            StormAudioToggleSwitch(
                coordinator,
                f"{device_unique_id}_dolby_virtualizer",
                f"{device_name} Dolby Virtualizer",
                device_info,
                "mdi:surround-sound",
                lambda device_state: device_state.dolby_virtualizer,
                lambda coordinator: coordinator.async_set_dolby_virtualizer(True),
                lambda coordinator: coordinator.async_set_dolby_virtualizer(False),
            ),
            StormAudioToggleSwitch(
                coordinator,
                f"{device_unique_id}_dialog_norm",
                f"{device_name} Dialog Norm",
                device_info,
                "mdi:message-text",
                lambda device_state: device_state.dialog_norm,
                lambda coordinator: coordinator.async_set_dialog_norm(True),
                lambda coordinator: coordinator.async_set_dialog_norm(False),
            ),
            StormAudioToggleSwitch(
                coordinator,
                f"{device_unique_id}_center_spread",
                f"{device_name} Center Spread",
                device_info,
                "mdi:arrow-expand-horizontal",
                lambda device_state: device_state.center_spread,
                lambda coordinator: coordinator.async_set_center_spread(True),
                lambda coordinator: coordinator.async_set_center_spread(False),
            ),
            StormAudioToggleSwitch(
                coordinator,
                f"{device_unique_id}_lfe_dim",
                f"{device_name} LFE Dim",
                device_info,
                "mdi:volume-vibrate",
                lambda device_state: device_state.lfe_dim,
                lambda coordinator: coordinator.async_set_lfe_dim(True),
                lambda coordinator: coordinator.async_set_lfe_dim(False),
            ),
        ]
    )

    # --- Per-zone switches (Mute, EQ, Binaural Mode) ---
    device_state = coordinator.data["device_state"]
    zones = device_state.zones if device_state is not None else None
    if zones:
        zone_entities = []
        for zone in zones:
            zone_entities.extend(
                [
                    StormAudioZoneToggleSwitch(
                        coordinator,
                        f"{device_unique_id}_zone{zone.id}_mute",
                        f"{device_name} {zone.name} Mute",
                        device_info,
                        "mdi:volume-mute",
                        zone.id,
                        lambda z: z.mute,
                        lambda coordinator, zone_id: coordinator.async_set_zone_mute(
                            zone_id, True
                        ),
                        lambda coordinator, zone_id: coordinator.async_set_zone_mute(
                            zone_id, False
                        ),
                    ),
                    StormAudioZoneToggleSwitch(
                        coordinator,
                        f"{device_unique_id}_zone{zone.id}_eq",
                        f"{device_name} {zone.name} EQ",
                        device_info,
                        "mdi:equalizer",
                        zone.id,
                        lambda z: z.eq,
                        lambda coordinator, zone_id: coordinator.async_set_zone_eq(
                            zone_id, True
                        ),
                        lambda coordinator, zone_id: coordinator.async_set_zone_eq(
                            zone_id, False
                        ),
                    ),
                    StormAudioZoneToggleSwitch(
                        coordinator,
                        f"{device_unique_id}_zone{zone.id}_binaural_mode",
                        f"{device_name} {zone.name} Binaural Mode",
                        device_info,
                        "mdi:headphones",
                        zone.id,
                        lambda z: z.binaural_mode,
                        lambda coordinator, zone_id: coordinator.async_set_zone_binaural_mode(
                            zone_id, True
                        ),
                        lambda coordinator, zone_id: coordinator.async_set_zone_binaural_mode(
                            zone_id, False
                        ),
                    ),
                ]
            )
        add_entities(zone_entities)

    # --- Per-trigger switches ---
    trigger_names = device_state.trigger_names if device_state is not None else None
    if trigger_names:
        trigger_entities = []
        for idx, trigger_name in enumerate(trigger_names):
            trigger_num = idx + 1
            trigger_entities.append(
                StormAudioTriggerSwitch(
                    coordinator,
                    f"{device_unique_id}_trigger{trigger_num}",
                    f"{device_name} Trigger: {trigger_name}",
                    device_info,
                    trigger_num,
                )
            )
        add_entities(trigger_entities)


class StormAudioMuteSwitch(CoordinatorEntity, SwitchEntity):
    """StormAudio mute switch."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_native_value = None

        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:volume-mute"
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

            self._attr_native_value = device_state.mute

    @property
    def is_on(self) -> bool:
        """Return the state of the switch (muted == True/"on")."""
        return self._attr_native_value

    async def async_turn_on(self) -> None:
        """Turn the switch on (mute)."""
        await self.coordinator.async_set_mute(True)

    async def async_turn_off(self) -> None:
        """Turn the switch off (unmute)."""
        await self.coordinator.async_set_mute(False)


class StormAudioPowerSwitch(CoordinatorEntity, SwitchEntity):
    """StormAudio power switch."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_native_value = None

        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:power"
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

        if device_state is not None:
            self._attr_native_value = device_state.processor_state in [
                ProcessorState.ON,
                ProcessorState.INITIALIZING,
            ]

    @property
    def is_on(self) -> bool:
        """Return the state of the switch (on == True/"on")."""
        return self._attr_native_value

    async def async_turn_on(self) -> None:
        """Turn the switch on."""
        await self.coordinator.async_set_power_state(PowerCommand.ON)

    async def async_turn_off(self) -> None:
        """Turn the switch off."""
        await self.coordinator.async_set_power_state(PowerCommand.OFF)


class StormAudioToggleSwitch(CoordinatorEntity, SwitchEntity):
    """Generic StormAudio boolean toggle switch (Dim, Dolby
    Virtualizer, Dialog Norm, Center Spread, LFE Dim)."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
        icon: str,
        get_value_fn,
        async_turn_on_fn,
        async_turn_off_fn,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_native_value = None

        self._attr_unique_id = unique_id
        self._attr_icon = icon
        self._attr_name = name

        self._attr_device_info = parent_device_info
        self._get_value_fn = get_value_fn
        self._async_turn_on_fn = async_turn_on_fn
        self._async_turn_off_fn = async_turn_off_fn

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
        else:
            self._attr_available = False

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._attr_native_value

    async def async_turn_on(self) -> None:
        """Turn the switch on."""
        await self._async_turn_on_fn(self.coordinator)

    async def async_turn_off(self) -> None:
        """Turn the switch off."""
        await self._async_turn_off_fn(self.coordinator)


def _find_zone(device_state: DeviceState, zone_id: int):
    """Look up a zone by ID in the current zones list."""
    if device_state is None or device_state.zones is None:
        return None
    for zone in device_state.zones:
        if zone.id == zone_id:
            return zone
    return None


class StormAudioZoneToggleSwitch(CoordinatorEntity, SwitchEntity):
    """Per-zone boolean toggle switch (Mute, EQ, Binaural Mode)."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
        icon: str,
        zone_id: int,
        get_zone_value_fn,
        async_turn_on_fn,
        async_turn_off_fn,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_native_value = None

        self._attr_unique_id = unique_id
        self._attr_icon = icon
        self._attr_name = name

        self._attr_device_info = parent_device_info
        self._attr_entity_registry_enabled_default = False
        self._zone_id = zone_id
        self._get_zone_value_fn = get_zone_value_fn
        self._async_turn_on_fn = async_turn_on_fn
        self._async_turn_off_fn = async_turn_off_fn

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
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._attr_native_value

    async def async_turn_on(self) -> None:
        """Turn the switch on."""
        await self._async_turn_on_fn(self.coordinator, self._zone_id)

    async def async_turn_off(self) -> None:
        """Turn the switch off."""
        await self._async_turn_off_fn(self.coordinator, self._zone_id)


class StormAudioTriggerSwitch(CoordinatorEntity, SwitchEntity):
    """12V trigger output switch."""

    def __init__(
        self,
        coordinator: StormAudioCoordinator,
        unique_id: str,
        name: str,
        parent_device_info: DeviceInfo,
        trigger_num: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_native_value = None

        self._attr_unique_id = unique_id
        self._attr_icon = "mdi:electric-switch"
        self._attr_name = name

        self._attr_device_info = parent_device_info
        self._attr_entity_registry_enabled_default = False
        self._trigger_num = trigger_num

        self._set_state_from_device()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_state_from_device()
        self.async_write_ha_state()

    def _set_state_from_device(self):
        device_state: DeviceState = self.coordinator.data["device_state"]
        self._attr_available = self.coordinator.connected

        value = (
            device_state.trigger_states.get(self._trigger_num)
            if device_state is not None
            else None
        )
        if value is not None:
            self._attr_native_value = value
        else:
            self._attr_available = False

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self._attr_native_value

    async def async_turn_on(self) -> None:
        """Turn the switch on."""
        await self.coordinator.async_set_trigger(self._trigger_num, True)

    async def async_turn_off(self) -> None:
        """Turn the switch off."""
        await self.coordinator.async_set_trigger(self._trigger_num, False)
