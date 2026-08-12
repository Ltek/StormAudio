# Home Assistant integration for StormAudio processors

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom component that provides an integration to the StormAudio processors.

## Entities

- `media_player` - main device control (power, volume, mute, source, sound mode)
- `switch`
  - Mute, Power
  - Dim, Dolby Virtualizer, Dialog Norm, Center Spread, LFE Dim
  - Per zone: Mute, EQ, Binaural Mode
  - Per trigger: on/off
- `select`
  - Source, Source (Zone 2), Preset
  - Dolby Mode, Auro Preset, SphereAudio Effect, Loudness
  - DRC, IMAX Mode (on/off/auto)
  - Front Panel Color, Front Panel Standby Delay
- `number`
  - Volume Level
  - Center Enhance, Surround Enhance, LFE Enhance, Bass, Treble,
    Brightness, LipSync
  - Auro Strength, Dialog Control
  - Front Panel Standby Brightness, Front Panel Active Brightness
  - Per zone: Volume, Bass, Treble, LipSync
- `sensor`
  - Surround Mode (+ `engaged` attribute), StormXT
  - Video Resolution, Video Encoding, Video Refresh Rate, Video Input,
    Video Sync, Video Copy Protection, Video Color Space, Video Color
    Depth, Video Mode
  - Active Speaker Config, Sample Rate, Stream Type, Channel Format

Per-zone and per-trigger entities are created dynamically based on what
the StormAudio device reports at startup (its `zones.list` / `trigger.list` broadcasts).
If you add or rename zones/triggers on the unit itself, restart the
integration (or Home Assistant) to pick up the change.

The protocol client (`stormaudio_telnet/`) is vendored directly in
this integration rather than pulled in as a separate pip dependency.

## Notes

- Video info reads HDMI OUT 1 only (the primary display output on nearly
  all installs). If your primary display is on HDMI OUT 2, the
  `hdmi2_*` equivalents would need to be added to `DeviceState` and
  wired into `sensor.py` the same way `hdmi1_*` is done.
- Zone sub-controls (mute/bass/treble/eq/binaural mode/lipsync) rely on
  the StormAudio device resending its full `zones.list` broadcast whenever any zone
  field changes (per the API doc) rather than parsing each zone's
  individual per-field echo separately.
- Some controls require licenses/hardware to be present (StormXT,
  SphereAudio) - when not licensed, the StormAudio device returns `error`, which shows
  up as `unavailable` for the corresponding sensor/select rather than a
  numeric value.
- Front Panel Color isn't available on Bryston/Focal-branded units; the
  StormAudio device simply won't respond to that command on those units, so the select
  entity will just stay at "unknown" there.
