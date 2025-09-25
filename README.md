# Synth Controller

Raspberry-Pi based controller for a DIY synthesizer. The Pi scans a button matrix and rotary encoders, plays tones directly, and serves a modern web UI so every input can be remapped without touching Python code.

## Highlights

- **Realtime keyboard** – 12-key matrix mapped to musical notes with onboard audio playback (*simpleaudio*).
- **Live-configurable encoders** – assign each rotary encoder to `transpose`, `volume`, `waveform`, or leave it free.
- **FastAPI web console** – responsive UI to edit mappings, preview notes, and monitor the rig from any browser (`http://<pi-ip>:8080`).
- **Config sync** – changes are persisted to `synth/config.yaml`, ready to share across Pis via git.
- **Systemd friendly** – service definition plus install script to make the synth autostart on boot.

---

## Quick Start (Developer Preview)

Want to try the web UI without hardware? Install deps with [uv](https://github.com/astral-sh/uv) and run the dev server:

```bash
uv sync
uv run python -m synth.dev_web
```

Open `http://127.0.0.1:8080` to explore the UI. Note playback requires `simpleaudio`; if it is missing the backend will log a warning and skip audio while keeping the UI functional.

---

## Raspberry Pi Deployment

```bash
# 1. Clone + enter
sudo apt-get update
sudo apt-get install -y git curl
git clone https://github.com/tonycannotprogrammy/synth-controller.git
cd synth-controller

# 2. Provision (installs pigpio, python deps, systemd unit)
bash install_pi.sh
```

The service starts automatically. Visit `http://<pi-ip>:8080` to edit notes, encoder actions, and synth settings. All edits apply immediately and persist to `synth/config.yaml`.

> **Audio:** the project uses [`simpleaudio`](https://simpleaudio.readthedocs.io/) for lightweight playback. On Raspberry Pi OS this works out-of-the-box with ALSA. If you route audio elsewhere, adjust the ALSA default device accordingly.

---

## Web UI Overview

- **Keys panel** – change note assignments, trigger previews, and watch press/release in real time.
- **Encoders panel** – map actions and tweak step sizes on the fly; updates instantly feed the synth engine.
- **Synth section** – adjust waveform, volume, transpose, and envelope without restarts.

All updates broadcast over WebSocket so every connected browser stays in sync.

---

## Configuration File

`synth/config.yaml` now stores both hardware wiring and musical mappings:

```yaml
matrix:
  rows: {...}
  cols: {...}
  keys:
    - {id: MX1, row: ROW1, col: COL0, note: C4, label: C}
encoders:
  - {name: SW1, A: 26, B: 12, action: transpose, step: 1}
synth:
  waveform: sine
  volume: 0.7
  transpose: 0
  attack_ms: 5
  release_ms: 180
app:
  web_host: "0.0.0.0"
  web_port: 8080
  debounce_ms: 12
```

Changes made through the UI are validated, written back to this file, and load automatically the next time the service starts.

---

## Testing & Development Notes

- `run.sh` launches the full stack (matrix scan + web UI) – only use this on the Pi with `pigpiod` running.
- `python -m synth.dev_web` runs **only** the web layer for local UI work.
- The codebase targets Python 3.10+. Formatting sticks to ASCII for easy deployment.

---

## Contributing

1. `uv sync`
2. `uv run python -m synth.dev_web` (for UI) or `uv run python -m synth.app` (on hardware)
3. Edit configs via the web console and commit the resulting `synth/config.yaml` so other Pis inherit your mapping.

Happy patching!
