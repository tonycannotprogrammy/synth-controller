# Synth Controller

Python-basierte Logik für meinen DIY-Synthesizer auf dem Raspberry Pi.  
Funktionen:

- **Button-Matrix (3×6, 12 belegte Tasten)**
- **5 Rotary Encoder (jeweils A/B Pins)**
- **Web-App (FastAPI + WebSocket) zur Live-Anzeige und Konfiguration**
- **Autostart via systemd**
- **Einfaches Setup mit [uv](https://github.com/astral-sh/uv) (schneller Paketmanager)**

---

## Installation (auf dem Raspberry Pi)

```bash
# 1. Repo clonen
git clone https://github.com/tonycannotprogrammy/synth-controller.git
cd synth-controller

# 2. Setup Script starten
bash install_pi.sh