"""Classes for communicating with the StormAudio series sound processors

v0.9.0: adds Surround Mode, StormXT, HDMI video info, and audio trim
control (Bass/Treble/Brightness/Center-Surround-LFE Enhance/LipSync)
support.
"""

from __future__ import annotations
from asyncio import create_task, Event, sleep, Task, timeout, TimeoutError
from decimal import *
from enum import IntFlag, auto
import logging

import typing

import telnetlib3

from .constants import *
from .line_reader import *
# (already relative - these two files live alongside telnet_client.py in
# this vendored stormaudio_telnet/ subpackage)

_LOGGER = logging.getLogger("stormaudio.telnet_client")


class DeviceState:
    def __init__(
        self
    ):
        self.brand: str = None
        self.model: str = None
        self.power_command: PowerCommand = None
        self.processor_state: ProcessorState = None
        self.volume_db: Decimal = None
        self.mute: bool = None
        self.inputs: list(Input) = None
        self.input_id: int = None
        self.input_zone2_id: int = None
        self.zones: list(Zone) = None
        self.presets: list(Preset) = None
        self.preset_id: int = None
        # Surround mode (section 3.3.3)
        self.surround_mode_id: int = None
        self.allowed_mode_id: int = None
        # StormXT (section 3.4.13.8): True/False, or "error" (str) if the
        # StormXT license is not activated on this unit
        self.stormxt: bool | str = None
        # HDMI video info (section 3.9.1); output 1 only, since that's the
        # primary display output on nearly all installs. Add hdmi2_* fields
        # the same way if you need a second sensor for HDMI OUT 2.
        self.hdmi1_video_timing: str = None
        self.hdmi1_hdr: str = None
        # Audio trim controls (sections 3.4.5-3.4.12); all in dB (int),
        # except lipsync which is in ms (int)
        self.bass_db: int = None
        self.treble_db: int = None
        self.brightness_db: int = None
        self.center_enhance_db: int = None
        self.surround_enhance_db: int = None
        self.lfe_enhance_db: int = None
        self.lipsync_ms: int = None

        # --- Theater controls (section 3.4) ---
        self.dim: bool = None
        self.loudness: int = None  # 0-3
        self.drc: str = None  # "on" / "off" / "auto"
        self.dolby_mode: int = None  # 0-3
        self.dolby_virtualizer: bool = None
        self.imax_mode: str = None  # "on" / "off" / "auto"
        self.dialog_control_available: bool = None
        self.dialog_control_db: int = None  # 0-6
        self.dialog_norm: bool = None
        self.center_spread: bool = None
        self.auro_strength: int = None  # 0-15
        self.auro_preset: int = None  # 0-3
        self.sphereaudio_effect: int | str = None  # 0-4, or "error" if unlicensed
        self.lfe_dim: bool = None
        self.active_speaker_id: int = None

        # --- Stream info (section 3.8) ---
        self.sample_rate: str = None
        self.stream_type: str = None
        self.channel_format: str = None

        # --- HDMI info (section 3.9), output 1 only (primary display) ---
        self.hdmi1_video_input: str = None
        self.hdmi1_sync: str = None
        self.hdmi1_cp: str = None
        self.hdmi1_colorspace: str = None
        self.hdmi1_colordepth: str = None
        self.hdmi1_mode: str = None

        # --- Front panel (section 3.6.1) ---
        self.frontpanel_color: str = None
        self.frontpanel_stbybright: int = None
        self.frontpanel_actbright: int = None
        self.frontpanel_stbytime: int = None

        # --- Triggers (section 3.7.1) ---
        self.trigger_names: list[str] = None
        self.trigger_states: dict[int, bool] = {}


class Input:
    def __init__(
        self,
        name: str,
        id: int,
        video_in_id: VideoInputID,
        audio_in_id: AudioInputID,
        audio_zone2_in_id: AudioZone2InputID,
        delay_ms: Decimal
    ):
        self.name: str = name
        self.id: int = id
        self.video_in_id: VideoInputID = video_in_id
        self.audio_in_id: AudioInputID = audio_in_id
        self.audio_zone2_in_id: AudioZone2InputID = audio_zone2_in_id
        self.delay_ms: Decimal = delay_ms


class Zone:
    def __init__(
        self,
        id: int,
        name: str,
        zone_layout_type: ZoneLayoutType,
        zone_type: ZoneType,
        use_zone2_source: bool,
        volume_db: Decimal,
        delay_ms: Decimal,
        mute: bool,
        eq: bool = None,
        lipsync_ms: int = None,
        binaural_mode: bool = None,
        loudness: int = None,
        avzones: int = None,
        bass_db: int = None,
        treble_db: int = None
    ):
        self.name: str = name
        self.id: int = id
        self.zone_layout_type: VideoInputID = zone_layout_type
        self.zone_type: AudioInputID = zone_type
        self.use_zone2_source: AudioZone2InputID = use_zone2_source
        self.volume_db = volume_db
        self.delay_ms: Decimal = delay_ms
        self.mute: bool = mute
        # Extra fields from the zones.list message (see section 3.5.1)
        self.eq: bool = eq
        self.lipsync_ms: int = lipsync_ms
        self.binaural_mode: bool = binaural_mode
        self.loudness: int = loudness
        self.avzones: int = avzones
        self.bass_db: int = bass_db
        self.treble_db: int = treble_db


class Preset:
    def __init__(
        self,
        name: str,
        id: int,
        audio_zone_ids: list(int),
        sphereaudio_theater_enabled: bool
    ):
        self.name: str = name
        self.id: int = id
        self.audio_zone_ids: list(int) = audio_zone_ids
        self.sphereaudio_theater_enabled: bool = sphereaudio_theater_enabled


class ReadLinesResult(IntFlag):
    NONE = 0
    COMPLETE = auto()
    STATE_UPDATED = auto()
    INCOMPLETE = auto()
    IGNORED = auto()


class TelnetClient():
    """Represents a client for communicating with the telnet server of an
        StormAudio sound processor."""

    def __init__(
        self,
        host: str,
        async_on_device_state_updated,
        async_on_disconnected,
        async_on_raw_line_received=None
    ):
        self._device_state: DeviceState = DeviceState()
        self._reader = None
        self._writer = None
        self._host: str = host
        self._remaining_output: str = None
        self._read_lines: TokenizedLinesReader = None
        self._async_on_device_state_updated = async_on_device_state_updated
        self._async_on_disconnected = async_on_disconnected
        self._async_on_raw_line_received = async_on_raw_line_received
        self._keepalive_loop_task: Task = None
        self._keepalive_received: bool = False
        self._read_loop_finished: Event = Event()

    def get_device_state(
        self
    ) -> DeviceState:
        return self._device_state

    async def async_connect(
        self
    ) -> None:
        """Connects to the telnet server and reads data on the async
        event loop."""
        self._read_lines = TokenizedLinesReader()
        self._remaining_output = ''

        self._read_loop_finished.clear()

        try:
            async with timeout(5):
                self._reader, self._writer = await telnetlib3.open_connection(
                    self._host,
                    connect_minwait=0.0,
                    connect_maxwait=0.0,
                    shell=self._read_loop
                )
        except (TimeoutError, OSError) as exc:
            raise ConnectionError from exc

        self._keepalive_received = False
        self._keepalive_loop_task = create_task(self._keepalive_loop())

    async def _keepalive_loop(
        self
    ):
        while True:

            await self._async_send_command("ssp.keepalive")
            await sleep(5)

            if not self._keepalive_received:
                # disconnect will cancel this task
                create_task(self.async_disconnect())
            self._keepalive_received = False

    async def async_disconnect(
        self
    ) -> None:
        """Disconnects from the telnet server."""
        if self._keepalive_loop_task is not None:
            self._keepalive_loop_task.cancel()
            self._keepalive_loop_task = None
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        self._keepalive_received = False
        await self._read_loop_finished.wait()

    async def _read_loop(
        self,
        reader,
        writer
    ) -> None:
        """Async loop to read data received from the telnet server;
        sets device state as a result of data received."""

        exception: Exception = None
        while True:
            try:
                read_output = await reader.read(1024)
                if not read_output:
                    # EOF
                    break

                # Append new read output to any prior remaining output
                output = self._remaining_output + read_output

                # Parse the complete lines from the output
                output_lines = output.split('\n')

                # Add all complete lines to the read lines; excludes final
                # index, which is partial output (no CR yet)
                line_count = len(output_lines)
                if (line_count > 1):
                    if self._async_on_raw_line_received is not None:
                        for line_idx in range(0, line_count - 1):
                            await self._async_on_raw_line_received(
                                output_lines[line_idx])
                    self._read_lines.add_lines(output_lines[0: line_count - 1])

                # Save the remaining partial output
                self._remaining_output = output_lines[len(output_lines) - 1]

                state_updated: bool = False
                while self._read_lines.has_next_line():
                    read_result: ReadLinesResult = ReadLinesResult.NONE

                    read_result |= self._eval__line(
                        ['ssp', 'keepalive'],
                        self._eval_keepalive
                    )

                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'brand'],
                        lambda x: self._device_state.__setattr__('brand', x),
                        lambda x: x.strip('"')
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'model'],
                        lambda x: self._device_state.__setattr__('model', x),
                        lambda x: x.strip('"')
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'power'],
                        self._eval_power_command
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'procstate'],
                        self._eval_processor_state
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'vol'],
                        lambda x: self._device_state.__setattr__(
                            'volume_db', x),
                        lambda x: Decimal(x)
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'mute'],
                        self._eval_mute
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'input', 'start'],
                        self._eval_inputs
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'zones', 'start'],
                        self._eval_zones
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'preset', 'start'],
                        self._eval_presets
                    )

                    preset_read_result: ReadLinesResult = self._eval__single_bracket_field(
                        ['ssp', 'preset'],
                        lambda x: self._device_state.__setattr__(
                            'preset_id', x),
                        lambda x: int(x)
                    )
                    read_result |= preset_read_result
                    # If the preset changes, request the zones list explicitly; the StormAudio device
                    # does not refresh the available zones when the preset changes
                    if preset_read_result & ReadLinesResult.COMPLETE:
                        await self.async_request_zones()

                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'input'],
                        lambda x: self._device_state.__setattr__(
                            'input_id', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'inputZone2'],
                        lambda x: self._device_state.__setattr__(
                            'input_zone2_id', x),
                        lambda x: int(x)
                    )

                    # --- Surround mode (section 3.3.3) ---
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'surroundmode'],
                        lambda x: self._device_state.__setattr__(
                            'surround_mode_id', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'allowedmode'],
                        lambda x: self._device_state.__setattr__(
                            'allowed_mode_id', x),
                        lambda x: int(x)
                    )

                    # --- StormXT (section 3.4.13.8) ---
                    read_result |= self._eval__line(
                        ['ssp', 'stormxt'],
                        self._eval_stormxt
                    )

                    # --- HDMI 1 video info (section 3.9.1) ---
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'hdmi1', 'timing'],
                        lambda x: self._device_state.__setattr__(
                            'hdmi1_video_timing', x),
                        lambda x: x.strip('"')
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'hdmi1', 'hdr'],
                        lambda x: self._device_state.__setattr__(
                            'hdmi1_hdr', x),
                        lambda x: x.strip('"')
                    )

                    # --- Audio trim controls (sections 3.4.5-3.4.12) ---
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'bass'],
                        lambda x: self._device_state.__setattr__(
                            'bass_db', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'treble'],
                        lambda x: self._device_state.__setattr__(
                            'treble_db', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'brightness'],
                        lambda x: self._device_state.__setattr__(
                            'brightness_db', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'c_en'],
                        lambda x: self._device_state.__setattr__(
                            'center_enhance_db', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 's_en'],
                        lambda x: self._device_state.__setattr__(
                            'surround_enhance_db', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'lfe_en'],
                        lambda x: self._device_state.__setattr__(
                            'lfe_enhance_db', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'lipsync'],
                        lambda x: self._device_state.__setattr__(
                            'lipsync_ms', x),
                        lambda x: int(x)
                    )

                    # --- Additional theater controls (section 3.4) ---
                    read_result |= self._eval__line(
                        ['ssp', 'dim'],
                        self._eval_dim
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'loudness'],
                        lambda x: self._device_state.__setattr__(
                            'loudness', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'drc'],
                        self._eval_drc
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'dolbymode'],
                        lambda x: self._device_state.__setattr__(
                            'dolby_mode', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'dolbyvirtualizer'],
                        self._eval_dolby_virtualizer
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'IMAXMode'],
                        self._eval_imax_mode
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'dialogcontrol'],
                        self._eval_dialog_control
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'dialognorm'],
                        self._eval_dialog_norm
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'cspread'],
                        self._eval_center_spread
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'aurostrength'],
                        lambda x: self._device_state.__setattr__(
                            'auro_strength', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'auropreset'],
                        lambda x: self._device_state.__setattr__(
                            'auro_preset', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'spheraudioeffect'],
                        self._eval_sphereaudio_effect
                    )
                    read_result |= self._eval__line(
                        ['ssp', 'lfedim'],
                        self._eval_lfe_dim
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'speaker'],
                        lambda x: self._device_state.__setattr__(
                            'active_speaker_id', x),
                        lambda x: int(x)
                    )

                    # --- Stream info (section 3.8) ---
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'fs'],
                        lambda x: self._device_state.__setattr__(
                            'sample_rate', x),
                        lambda x: x
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'stream'],
                        lambda x: self._device_state.__setattr__(
                            'stream_type', x),
                        lambda x: x
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'format'],
                        lambda x: self._device_state.__setattr__(
                            'channel_format', x),
                        lambda x: x
                    )

                    # --- Additional HDMI 1 info (section 3.9.1) ---
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'hdmi1', 'input'],
                        lambda x: self._device_state.__setattr__(
                            'hdmi1_video_input', x),
                        lambda x: x.strip('"')
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'hdmi1', 'sync'],
                        lambda x: self._device_state.__setattr__(
                            'hdmi1_sync', x),
                        lambda x: x.strip('"')
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'hdmi1', 'cp'],
                        lambda x: self._device_state.__setattr__(
                            'hdmi1_cp', x),
                        lambda x: x.strip('"')
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'hdmi1', 'colorspace'],
                        lambda x: self._device_state.__setattr__(
                            'hdmi1_colorspace', x),
                        lambda x: x.strip('"')
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'hdmi1', 'colordepth'],
                        lambda x: self._device_state.__setattr__(
                            'hdmi1_colordepth', x),
                        lambda x: x.strip('"')
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'hdmi1', 'mode'],
                        lambda x: self._device_state.__setattr__(
                            'hdmi1_mode', x),
                        lambda x: x.strip('"')
                    )

                    # --- Front panel (section 3.6.1) ---
                    read_result |= self._eval__line(
                        ['ssp', 'frontpanel', 'color'],
                        self._eval_frontpanel_color
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'frontpanel', 'stbybright'],
                        lambda x: self._device_state.__setattr__(
                            'frontpanel_stbybright', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'frontpanel', 'actbright'],
                        lambda x: self._device_state.__setattr__(
                            'frontpanel_actbright', x),
                        lambda x: int(x)
                    )
                    read_result |= self._eval__single_bracket_field(
                        ['ssp', 'frontpanel', 'stbytime'],
                        lambda x: self._device_state.__setattr__(
                            'frontpanel_stbytime', x),
                        lambda x: int(x)
                    )

                    # --- Triggers (section 3.7.1) ---
                    read_result |= self._eval__line(
                        ['ssp', 'trigger', 'start'],
                        self._eval_triggers
                    )
                    for trigger_num in range(1, 9):
                        read_result |= self._eval__line(
                            ['ssp', f'trig{trigger_num}'],
                            self._make_eval_trigger_state(trigger_num)
                        )

                    # --- Zones (section 3.5.1): extra fields are parsed
                    # inside _eval_zones above; individual per-field zone
                    # echoes (e.g. ssp.zones.mute.[id,yy]) aren't parsed
                    # separately since the StormAudio device resends the full zones.list
                    # whenever any zone field changes (per section 3.5.1).

                    if read_result & ReadLinesResult.STATE_UPDATED:
                        # At least one line evaluator read data and updated state.
                        state_updated = True

                    if read_result & ReadLinesResult.INCOMPLETE:
                        # At least one line evaluator didn't have enough lines.
                        break

                    if read_result == ReadLinesResult.IGNORED:
                        # All evaluators ignored the line; remove it.
                        self._read_lines.read_next_line()
                        self._read_lines.consume_read_lines()

                if state_updated:
                    await self._async_notify_device_state_updated()
            except Exception as ex:
                create_task(self.async_disconnect())
                exception = ex
                break

        self._read_loop_finished.set()
        self._reader = None
        await self._async_notify_disconnected()

        if exception is not None:
            raise RuntimeError("Error in reader loop") from exception

    async def _async_notify_disconnected(
        self
    ):
        await self._async_on_disconnected()

    async def _async_notify_device_state_updated(
        self
    ):
        await self._async_on_device_state_updated()

    async def _async_send_command(
        self,
        command: str
    ) -> None:
        """Sends given command to the server. Automatically appends
            CR to the command string."""
        self._writer.write(command + '\n')
        await self._writer.drain()

    async def async_set_power_command(self, power_command: PowerCommand):
        power_command_string: str = 'on' if power_command == PowerCommand.ON else 'off'
        await self._async_send_command(f'ssp.power.{power_command_string}')

    async def async_request_zones(self):
        await self._async_send_command('ssp.zones.list')

    async def async_set_mute(self, mute: bool):
        mute_command: str = 'on' if mute else 'off'
        await self._async_send_command(f'ssp.mute.{mute_command}')
    
    async def async_toggle_mute(self):
        await self._async_send_command(f'ssp.mute.toggle')

    async def async_set_volume(self, volume_db: Decimal):
        await self._async_send_command(f'ssp.vol.[{volume_db}]')

    async def async_set_input_id(self, input_id: int):
        await self._async_send_command(f'ssp.input.[{input_id}]')

    async def async_set_input_zone2_id(self, input_zone2_id: int):
        await self._async_send_command(f'ssp.inputZone2.[{input_zone2_id}]')

    async def async_set_preset_id(self, preset_id: int):
        await self._async_send_command(f'ssp.preset.[{preset_id}]')

    async def async_set_surround_mode_id(self, surround_mode_id: int):
        """Set preferred upmix/surround mode. See section 3.3.3 - the mode
        may not actually engage; check allowed_mode_id / surround_mode_id
        equality on DeviceState to know if it's really active."""
        await self._async_send_command(f'ssp.surroundmode.[{surround_mode_id}]')

    async def async_set_stormxt(self, on: bool):
        stormxt_command: str = 'on' if on else 'off'
        await self._async_send_command(f'ssp.stormxt.{stormxt_command}')

    async def async_toggle_stormxt(self):
        await self._async_send_command('ssp.stormxt.toggle')

    async def async_set_bass(self, bass_db: int):
        """Set bass tone control, -6..6 dB step 1 (further limited by the
        installer-configured Audio Control Range MAX on the unit)."""
        await self._async_send_command(f'ssp.bass.[{bass_db}]')

    async def async_set_treble(self, treble_db: int):
        """Set treble tone control, -6..6 dB step 1."""
        await self._async_send_command(f'ssp.treble.[{treble_db}]')

    async def async_set_brightness(self, brightness_db: int):
        """Set brightness control, -6..6 dB step 1."""
        await self._async_send_command(f'ssp.brightness.[{brightness_db}]')

    async def async_set_center_enhance(self, center_enhance_db: int):
        """Set center enhance control, -6..6 dB step 1."""
        await self._async_send_command(f'ssp.c_en.[{center_enhance_db}]')

    async def async_set_surround_enhance(self, surround_enhance_db: int):
        """Set surround enhance control, -6..6 dB step 1."""
        await self._async_send_command(f'ssp.s_en.[{surround_enhance_db}]')

    async def async_set_lfe_enhance(self, lfe_enhance_db: int):
        """Set LFE enhance control, -6..6 dB step 1."""
        await self._async_send_command(f'ssp.lfe_en.[{lfe_enhance_db}]')

    async def async_set_lipsync(self, lipsync_ms: int):
        """Set lip sync delay in ms. Range per the API doc is
        -(Inputs AV Delay + Settings AV Zone Delay) to 100ms, step 1ms -
        i.e. the true minimum depends on your installer-configured delay
        settings, so no fixed floor is enforced here."""
        await self._async_send_command(f'ssp.lipsync.[{lipsync_ms}]')

    # --- Additional theater controls (section 3.4) ---

    async def async_set_dim(self, on: bool):
        await self._async_send_command(f'ssp.dim.{"on" if on else "off"}')

    async def async_toggle_dim(self):
        await self._async_send_command('ssp.dim.toggle')

    async def async_set_loudness(self, level: int):
        """0=Off, 1=Low, 2=Medium, 3=Full."""
        await self._async_send_command(f'ssp.loudness.[{level}]')

    async def async_set_drc(self, mode: str):
        """mode is 'on', 'off', or 'auto'."""
        await self._async_send_command(f'ssp.drc.{mode}')

    async def async_set_dolby_mode(self, mode: int):
        """0=Off, 1=Movie, 2=Music, 3=Night."""
        await self._async_send_command(f'ssp.dolbymode.[{mode}]')

    async def async_set_dolby_virtualizer(self, on: bool):
        await self._async_send_command(
            f'ssp.dolbyvirtualizer.{"on" if on else "off"}')

    async def async_toggle_dolby_virtualizer(self):
        await self._async_send_command('ssp.dolbyvirtualizer.toggle')

    async def async_set_imax_mode(self, mode: str):
        """mode is 'on', 'off', or 'auto'. Note the StormAudio device's documented quirk:
        the response to 'on' is 'ssp.IMAXMode.auto', not '...on' - this is
        just how the unit echoes it, not a bug in this client."""
        await self._async_send_command(f'ssp.IMAXMode.{mode}')

    async def async_set_dialog_control(self, dialog_control_db: int):
        """0-6 dB; only takes effect when dialog_control_available is True
        on DeviceState (DTS:X streams with dialog control support)."""
        await self._async_send_command(f'ssp.dialogcontrol.[{dialog_control_db}]')

    async def async_set_dialog_norm(self, on: bool):
        await self._async_send_command(f'ssp.dialognorm.{"on" if on else "off"}')

    async def async_toggle_dialog_norm(self):
        await self._async_send_command('ssp.dialognorm.toggle')

    async def async_set_center_spread(self, on: bool):
        await self._async_send_command(f'ssp.cspread.{"on" if on else "off"}')

    async def async_toggle_center_spread(self):
        await self._async_send_command('ssp.cspread.toggle')

    async def async_set_auro_strength(self, strength: int):
        """0-15; only meaningful when Auro-Matic surround mode is engaged."""
        await self._async_send_command(f'ssp.aurostrength.[{strength}]')

    async def async_set_auro_preset(self, preset_id: int):
        """0=Small, 1=Medium, 2=Large, 3=Speech."""
        await self._async_send_command(f'ssp.auropreset.[{preset_id}]')

    async def async_set_sphereaudio_effect(self, effect_id: int):
        """0=Bypass, 1=Lounge, 2=Home Cinema, 3=Concert, 4=Cinema.
        Requires the SphereAudio license; returns 'error' otherwise."""
        await self._async_send_command(f'ssp.spheraudioeffect.[{effect_id}]')

    async def async_set_lfe_dim(self, on: bool):
        await self._async_send_command(f'ssp.lfedim.{"on" if on else "off"}')

    async def async_toggle_lfe_dim(self):
        await self._async_send_command('ssp.lfedim.toggle')

    # --- Front panel (section 3.6.1) ---

    async def async_set_frontpanel_color(self, color: str):
        """color is one of: blue, red, green, white, magenta, orange.
        Not available on Bryston/Focal-branded units."""
        await self._async_send_command(f'ssp.frontpanel.color.[{color}]')

    async def async_set_frontpanel_stbybright(self, brightness: int):
        """0-100, step 10."""
        await self._async_send_command(f'ssp.frontpanel.stbybright.[{brightness}]')

    async def async_set_frontpanel_actbright(self, brightness: int):
        """0-100, step 10."""
        await self._async_send_command(f'ssp.frontpanel.actbright.[{brightness}]')

    async def async_set_frontpanel_stbytime(self, seconds: int):
        """One of: 2, 5, 10, 20, 30, 60."""
        await self._async_send_command(f'ssp.frontpanel.stbytime.[{seconds}]')

    # --- Triggers (section 3.7.1) ---

    async def async_request_triggers(self):
        await self._async_send_command('ssp.trigger.list')

    async def async_set_trigger(self, trigger_num: int, on: bool):
        await self._async_send_command(
            f'ssp.trig{trigger_num}.{"on" if on else "off"}')

    async def async_toggle_trigger(self, trigger_num: int):
        await self._async_send_command(f'ssp.trig{trigger_num}.toggle')

    # --- Zones (section 3.5.1) ---

    async def async_set_zone_volume(self, zone_id: int, volume_db: Decimal):
        await self._async_send_command(f'ssp.zones.volume.[{zone_id}, {volume_db}]')

    async def async_set_zone_mute(self, zone_id: int, mute: bool):
        await self._async_send_command(
            f'ssp.zones.mute.[{zone_id}, {1 if mute else 0}]')

    async def async_toggle_zone_mute(self, zone_id: int):
        await self._async_send_command(f'ssp.zones.mute.toggle.[{zone_id}]')

    async def async_set_zone_bass(self, zone_id: int, bass_db: int):
        await self._async_send_command(f'ssp.zones.bass.[{zone_id}, {bass_db}]')

    async def async_set_zone_treble(self, zone_id: int, treble_db: int):
        await self._async_send_command(f'ssp.zones.treble.[{zone_id}, {treble_db}]')

    async def async_set_zone_lipsync(self, zone_id: int, lipsync_ms: int):
        await self._async_send_command(
            f'ssp.zones.lipsync.[{zone_id}, {lipsync_ms}]')

    async def async_set_zone_eq(self, zone_id: int, eq_on: bool):
        await self._async_send_command(
            f'ssp.zones.eq.[{zone_id}, {1 if eq_on else 0}]')

    async def async_toggle_zone_eq(self, zone_id: int):
        await self._async_send_command(f'ssp.zones.eq.toggle.[{zone_id}]')

    async def async_set_zone_binaural_mode(self, zone_id: int, binaural: bool):
        await self._async_send_command(
            f'ssp.zones.mode.[{zone_id}, {1 if binaural else 0}]')

    async def async_toggle_zone_binaural_mode(self, zone_id: int):
        await self._async_send_command(f'ssp.zones.mode.toggle.[{zone_id}]')

    async def async_set_zone_loudness(self, zone_id: int, level: int):
        await self._async_send_command(f'ssp.zones.loudness.[{zone_id}, {level}]')

    def _eval__line(
        self,
        expected_tokens: list(str),
        continue_fn,
    ) -> ReadLinesResult:
        if self._read_lines.has_next_line():
            line: TokenizedLineReader = self._read_lines.read_next_line()
            if line.pop_next_tokens_if_equal(expected=expected_tokens):
                try:
                    read_result: ReadLinesResult = continue_fn(line)
                except Exception:
                    # A parsing bug in one evaluator (e.g. an unexpected
                    # field count/format from this firmware) shouldn't be
                    # allowed to tear down the whole connection - log it
                    # and drop this one command instead. Worst case, this
                    # one update is missed and picked up on the next
                    # broadcast of the same value.
                    _LOGGER.warning(
                        "Failed to parse StormAudio device line for %s, skipping it",
                        expected_tokens,
                        exc_info=True,
                    )
                    self._read_lines.reset_read_lines()
                    return ReadLinesResult.IGNORED
                if read_result & ReadLinesResult.COMPLETE:
                    self._read_lines.consume_read_lines()
                else:
                    self._read_lines.reset_read_lines()
                return read_result
            self._read_lines.reset_read_lines()
            return ReadLinesResult.IGNORED
        return ReadLinesResult.INCOMPLETE

    def _eval_keepalive(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        self._keepalive_received = True
        return ReadLinesResult.COMPLETE

    def _eval__single_bracket_field(
        self,
        expected_tokens: list(str),
        set_fn,
        convert_fn
    ) -> ReadLinesResult:
        def parse_bracket_field(line: TokenizedLineReader):
            bracket_fields: list(str) = line.pop_next_token()
            if type(bracket_fields) is list:
                set_fn(convert_fn(bracket_fields[0]))
                return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
            return ReadLinesResult.IGNORED

        return self._eval__line(
            expected_tokens=expected_tokens,
            continue_fn=parse_bracket_field
        )

    def _eval_mute(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('on'):
            self._device_state.mute = True
        elif line.pop_next_token_if_equal('off'):
            self._device_state.mute = False
        else:
            return ReadLinesResult.IGNORED
        return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED

    def _eval_stormxt(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('on'):
            self._device_state.stormxt = True
        elif line.pop_next_token_if_equal('off'):
            self._device_state.stormxt = False
        elif line.pop_next_token_if_equal('error'):
            # StormXT license not activated on this unit
            self._device_state.stormxt = 'error'
        else:
            return ReadLinesResult.IGNORED
        return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED

    def _eval_dim(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('on'):
            self._device_state.dim = True
        elif line.pop_next_token_if_equal('off'):
            self._device_state.dim = False
        else:
            return ReadLinesResult.IGNORED
        return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED

    def _eval_drc(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('on'):
            self._device_state.drc = 'on'
        elif line.pop_next_token_if_equal('off'):
            self._device_state.drc = 'off'
        elif line.pop_next_token_if_equal('auto'):
            self._device_state.drc = 'auto'
        else:
            return ReadLinesResult.IGNORED
        return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED

    def _eval_dolby_virtualizer(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('on'):
            self._device_state.dolby_virtualizer = True
        elif line.pop_next_token_if_equal('off'):
            self._device_state.dolby_virtualizer = False
        else:
            return ReadLinesResult.IGNORED
        return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED

    def _eval_imax_mode(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('on'):
            self._device_state.imax_mode = 'on'
        elif line.pop_next_token_if_equal('off'):
            self._device_state.imax_mode = 'off'
        elif line.pop_next_token_if_equal('auto'):
            self._device_state.imax_mode = 'auto'
        else:
            return ReadLinesResult.IGNORED
        return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED

    def _eval_dialog_control(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        # ssp.dialogcontrol.[0/1, X] - a 2-value bracket field
        bracket_fields: list(str) = line.pop_next_token()
        if type(bracket_fields) is list and len(bracket_fields) >= 2:
            self._device_state.dialog_control_available = (
                bracket_fields[0].strip() == '1'
            )
            self._device_state.dialog_control_db = int(bracket_fields[1])
            return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
        return ReadLinesResult.IGNORED

    def _eval_dialog_norm(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('on'):
            self._device_state.dialog_norm = True
        elif line.pop_next_token_if_equal('off'):
            self._device_state.dialog_norm = False
        else:
            return ReadLinesResult.IGNORED
        return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED

    def _eval_center_spread(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('on'):
            self._device_state.center_spread = True
        elif line.pop_next_token_if_equal('off'):
            self._device_state.center_spread = False
        else:
            return ReadLinesResult.IGNORED
        return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED

    def _eval_sphereaudio_effect(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('error'):
            # SphereAudio license not activated on this unit
            self._device_state.sphereaudio_effect = 'error'
            return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
        bracket_fields: list(str) = line.pop_next_token()
        if type(bracket_fields) is list:
            self._device_state.sphereaudio_effect = int(bracket_fields[0])
            return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
        return ReadLinesResult.IGNORED

    def _eval_lfe_dim(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('on'):
            self._device_state.lfe_dim = True
        elif line.pop_next_token_if_equal('off'):
            self._device_state.lfe_dim = False
        else:
            return ReadLinesResult.IGNORED
        return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED

    def _eval_frontpanel_color(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        # Response is a plain token (not bracketed), e.g. "ssp.frontpanel.color.blue"
        for color in FRONT_PANEL_COLORS:
            if line.pop_next_token_if_equal(color):
                self._device_state.frontpanel_color = color
                return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
        return ReadLinesResult.IGNORED

    def _eval_triggers(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        new_trigger_names: list(str) = []
        while self._read_lines.has_next_line():
            line = self._read_lines.read_next_line()
            if line.pop_next_tokens_if_equal(['ssp', 'trigger', 'list']):
                bracket_fields: list(str) = line.pop_next_token()
                if type(bracket_fields) is list:
                    new_trigger_names.append(bracket_fields[0].strip('"'))
                else:
                    return ReadLinesResult.IGNORED
            elif line.pop_next_tokens_if_equal(['ssp', 'trigger', 'end']):
                self._device_state.trigger_names = new_trigger_names
                return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
            else:
                return ReadLinesResult.IGNORED
        return ReadLinesResult.INCOMPLETE

    def _make_eval_trigger_state(self, trigger_num: int):
        """Returns an eval function for ssp.trigX on/off, closed over the
        trigger number (X can't be a wildcard in the token-matching
        scheme, so we register one of these per trigger 1-8)."""
        def eval_trigger_state(line: TokenizedLineReader) -> ReadLinesResult:
            if line.pop_next_token_if_equal('on'):
                self._device_state.trigger_states[trigger_num] = True
            elif line.pop_next_token_if_equal('off'):
                self._device_state.trigger_states[trigger_num] = False
            else:
                return ReadLinesResult.IGNORED
            return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
        return eval_trigger_state

    def _eval_power_command(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        if line.pop_next_token_if_equal('on'):
            self._device_state.power_command = PowerCommand.ON
        elif line.pop_next_token_if_equal('off'):
            self._device_state.power_command = PowerCommand.OFF
        else:
            return ReadLinesResult.IGNORED
        return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED

    def _eval_processor_state(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        bracket_fields: list(str) = line.pop_next_token()
        if type(bracket_fields) is list:
            if bracket_fields[0] == '0':
                self._device_state.processor_state = ProcessorState.OFF
            elif bracket_fields[0] == '1':
                self._device_state.processor_state = ProcessorState.INITIALIZING \
                    if self._device_state.power_command == PowerCommand.ON \
                    else ProcessorState.SHUTTING_DOWN
            elif bracket_fields[0] == '2':
                self._device_state.processor_state = ProcessorState.ON
            else:
                return ReadLinesResult.IGNORED
            return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
        return ReadLinesResult.IGNORED

    def _eval_inputs(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        new_inputs: list(Input) = []
        while self._read_lines.has_next_line():
            line = self._read_lines.read_next_line()
            if line.pop_next_tokens_if_equal(['ssp', 'input', 'list']):
                bracket_fields: list(str) = line.pop_next_token()
                if type(bracket_fields) is list:
                    input = Input(
                        name=bracket_fields[0].strip('"'),
                        id=int(bracket_fields[1]),
                        video_in_id=VideoInputID(
                            int(bracket_fields[2])),
                        audio_in_id=AudioInputID(
                            int(bracket_fields[3])),
                        audio_zone2_in_id=AudioZone2InputID(
                            int(bracket_fields[4])),
                        delay_ms=Decimal(bracket_fields[6])
                    )
                    new_inputs.append(input)
                else:
                    return ReadLinesResult.IGNORED
            elif line.pop_next_tokens_if_equal(['ssp', 'input', 'end']):
                # set input list
                self._device_state.inputs = new_inputs
                return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
            else:
                return ReadLinesResult.IGNORED
        return ReadLinesResult.INCOMPLETE

    def _eval_zones(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        new_zones: list(Zone) = []
        while self._read_lines.has_next_line():
            line = self._read_lines.read_next_line()
            if line.pop_next_tokens_if_equal(['ssp', 'zones', 'list']):
                bracket_fields: list(str) = line.pop_next_token()
                if type(bracket_fields) is list:
                    def field(idx):
                        # Fields beyond the core 7 (id/name/layout/type/
                        # use_zone2/volume/delay) are best-effort: not all
                        # firmware versions send the same number of extra
                        # columns, so a short list here shouldn't take
                        # down the connection - it just means those extra
                        # Zone attributes stay None for this zone.
                        return bracket_fields[idx] if idx < len(bracket_fields) else None

                    def as_int(idx):
                        v = field(idx)
                        return int(v) if v is not None else None

                    def as_bool(idx):
                        v = field(idx)
                        return bool(int(v)) if v is not None else None

                    zone = Zone(
                        id=int(bracket_fields[0]),
                        name=bracket_fields[1].strip('"'),
                        zone_layout_type=ZoneLayoutType(
                            int(bracket_fields[2])),
                        zone_type=ZoneType(
                            int(bracket_fields[3])),
                        use_zone2_source=bool(int(bracket_fields[4])),
                        volume_db=Decimal(bracket_fields[5]),
                        delay_ms=Decimal(bracket_fields[6]),
                        eq=as_bool(7),
                        lipsync_ms=as_int(8),
                        binaural_mode=as_bool(9),
                        mute=as_bool(10) if as_bool(10) is not None else False,
                        loudness=as_int(11),
                        avzones=as_int(12),
                        bass_db=as_int(13),
                        treble_db=as_int(14)
                    )
                    new_zones.append(zone)
                else:
                    return ReadLinesResult.IGNORED
            elif line.pop_next_tokens_if_equal(['ssp', 'zones', 'end']):
                # set input list
                self._device_state.zones = new_zones
                return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
            else:
                return ReadLinesResult.IGNORED
        return ReadLinesResult.INCOMPLETE

    def _parse_audio_zone_ids(self, bracket_field: str):
        bracket_field_token = bracket_field.strip('"["').strip('"]"')
        bracket_field_tokens: list[str] = []
        if len(bracket_field_token) > 0:
            bracket_field_tokens = bracket_field_token.split('","')
        return list(map(lambda x: int(x), bracket_field_tokens))

    def _eval_presets(
        self,
        line: TokenizedLineReader
    ) -> ReadLinesResult:
        new_presets: list(Preset) = []
        while self._read_lines.has_next_line():
            line = self._read_lines.read_next_line()
            if line.pop_next_tokens_if_equal(['ssp', 'preset', 'list']):
                bracket_fields: list(str) = line.pop_next_token()
                if type(bracket_fields) is list:
                    preset = Preset(
                        name=bracket_fields[0].strip('"'),
                        id=int(bracket_fields[1]),
                        audio_zone_ids=self._parse_audio_zone_ids(
                            bracket_fields[2]),
                        sphereaudio_theater_enabled=bool(
                            int(bracket_fields[3]))
                    )
                    new_presets.append(preset)
                else:
                    return ReadLinesResult.IGNORED
            elif line.pop_next_tokens_if_equal(['ssp', 'preset', 'end']):
                # set preset list
                self._device_state.presets = new_presets
                return ReadLinesResult.COMPLETE | ReadLinesResult.STATE_UPDATED
            else:
                return ReadLinesResult.IGNORED
        return ReadLinesResult.INCOMPLETE
