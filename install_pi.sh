#!/usr/bin/env bash
set -euo pipefail

# 1) uv installieren (falls nicht vorhanden)
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# 2) pigpio installieren + daemon aktivieren
sudo apt-get update
sudo apt-get install -y pigpio
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

# 3) Repo-Pfad anpassen, falls du anders klonst
cd /home/pi/synth-controller

# 4) Abhängigkeiten synchronisieren
uv sync

# 5) systemd Service installieren
sudo cp systemd/synth.service /etc/systemd/system/synth.service
sudo systemctl daemon-reload
sudo systemctl enable synth.service
sudo systemctl start synth.service

echo "Fertig. Web-UI: http://<Pi-IP>:8080/"