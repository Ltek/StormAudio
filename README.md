# Home Assistant integration for StormAudio processors

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Ltek&repository=StormAudio&category=integration)

Home Assistant custom component integration for StormAudio, Focal and Bryston processors.



## Supported devices

Integration supports the StormAudio family of processors that use the published TCP/IP API (port 23,
firmware 4.6r1 or later) platform as of August 2026:

- StormAudio ISP and ISR series 
- Focal Astral 16
- Bryston SP4

Focal and Bryston branded units share the same API, with one documented exception: Front Panel
Color isn't available on those brands.

This is the most feature rich, and robust Home Assistant integration for StormAudio.

## Installation

This integration is not in the default HACS store, so install it as a HACS
**custom repository** (recommended) or copy the files in manually.

### HACS (recommended)

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Ltek&repository=StormAudio&category=integration)

1. Click the button above (it opens HACS on your Home Assistant and
   pre-fills this repository), **or** go to HACS → ⋮ (top-right menu) →
   **Custom repositories** and add `https://github.com/Ltek/StormAudio`
   with category **Integration**.
2. Find **StormAudio** in the HACS list and click **Download**.
3. **Restart Home Assistant** (Settings → System → Restart).
4. Add the integration: Settings → Devices & Services → **Add
   Integration** → search for **StormAudio**, then enter your processor's
   host/IP and a name.

### Manual

1. Copy the integration folder to your Home Assistant config directory so
   the files land at:
   `/config/custom_components/stormaudio/`
   (i.e. `/config/custom_components/stormaudio/manifest.json`,
   `.../__init__.py`, `.../media_player.py`, `.../stormaudio_telnet/`, etc.)
2. **Restart Home Assistant** (Settings → System → Restart).
3. Add the integration: Settings → Devices & Services → **Add
   Integration** → search for **StormAudio**, then enter your processor's
   host/IP and a name.

> A **restart is required** after installing or updating this integration -
> it loads as Python code at Home Assistant startup, so a config-entry
> "Reload" will not pick up new code. (Unlike a dashboard card, an
> integration is not registered under Dashboards → Resources and does not
> need a browser refresh.)

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
    Depth, Video Mode (one set per HDMI output - see Notes)
  - Active Speaker Config, Sample Rate, Stream Type, Channel Format

Per-zone and per-trigger entities are created dynamically based on what
the StormAudio device reports at startup (its `zones.list` / `trigger.list` broadcasts).
If you add or rename zones/triggers on the unit itself, restart the
integration (or Home Assistant) to pick up the change.

The protocol client (`stormaudio_telnet/`) is vendored directly in
this integration rather than pulled in as a separate pip dependency.

## Notes

- Video info is read for every HDMI output listed in `HDMI_OUTPUT_IDS`
  (`stormaudio_telnet/constants.py`) - HDMI OUT 1 and OUT 2 by default.
  The HDMI OUT 1 sensors are enabled by default. The HDMI OUT 2 sensors (named
  `... Video Resolution (HDMI OUT 2)`, etc.) are **created disabled**;
  if your display is on HDMI OUT 2 or you run dual displays, enable the
  ones you want from the entity's settings (Settings → Devices &
  Services → StormAudio → entity → gear icon → Enable). No code change or
  restart config is needed. If a future unit exposes more than two HDMI
  outputs, add the output number to `HDMI_OUTPUT_IDS` and the client and
  sensors pick it up automatically.
- Zone sub-controls (mute/bass/treble/eq/binaural mode/lipsync) rely on
  the StormAudio device resending its full `zones.list` broadcast whenever any zone
  field changes (per the API doc) rather than parsing each zone's
  individual per-field echo separately.
- Some controls require licenses/hardware to be present (StormXT,
  SphereAudio) - when not licensed, the StormAudio device returns `error`, which shows
  up as `unavailable` for the corresponding sensor/select rather than a
  numeric value.
- For Bryston/Focal-branded units, Front Panel Color isn't available; 
  these devices do not respond to that command so the entity will always show "unknown".
