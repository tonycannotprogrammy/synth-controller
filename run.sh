#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Sync deps (fast) und starten
uv sync
exec uv run python -m synth.app