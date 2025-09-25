from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from .audio import NoteSynth, note_to_frequency
from .config_store import (
    ConfigStore,
    ControllerConfig,
    EncoderConfig,
    KeyConfig,
    SUPPORTED_WAVEFORMS,
)

LOGGER = logging.getLogger(__name__)


class SynthController:
    """Coordinates hardware events, audio playback and runtime configuration."""

    def __init__(self, store: ConfigStore, synth: NoteSynth | None = None) -> None:
        self.store = store
        self.synth = synth or NoteSynth()
        self.config = self.store.get_cached()
        self.key_lookup: Dict[str, KeyConfig] = {}
        self.encoder_lookup: Dict[str, EncoderConfig] = {}
        self.key_state: Dict[str, bool] = {}
        self.encoder_state: Dict[str, Any] = {}
        self.live_settings: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._apply_config(self.config)

    # configuration -----------------------------------------------------------------
    def _apply_config(self, config: ControllerConfig) -> None:
        self.config = config
        self.key_lookup = {item.id: item for item in config.matrix.keys}
        self.encoder_lookup = {enc.name: enc for enc in config.encoders}
        self.key_state = {item.id: False for item in config.matrix.keys}
        self.encoder_state = {}
        self.synth.set_key_notes({item.id: item.note for item in config.matrix.keys})
        settings = config.synth
        self.live_settings = {
            "waveform": settings.waveform,
            "volume": settings.volume,
            "transpose": settings.transpose,
            "attack_ms": settings.attack_ms,
            "release_ms": settings.release_ms,
        }
        self.synth.set_waveform(settings.waveform)
        self.synth.set_volume(settings.volume)
        self.synth.set_transpose(settings.transpose)
        self.synth.set_envelope(settings.attack_ms, settings.release_ms)

    async def reload(self) -> ControllerConfig:
        async with self._lock:
            config = self.store.load()
            self._apply_config(config)
            return config

    async def replace(self, config_payload: dict) -> ControllerConfig:
        async with self._lock:
            config = self.store.save(config_payload)
            self._apply_config(config)
            return config

    async def update_part(self, payload: dict) -> ControllerConfig:
        async with self._lock:
            config = self.store.update(payload)
            self._apply_config(config)
            return config

    # queries -----------------------------------------------------------------------
    def get_public_config(self) -> dict:
        return self.config.jsonable()

    def get_runtime_state(self) -> dict:
        return {
            "keys": self.key_state,
            "encoders": self.encoder_state,
            "synth": self.live_settings,
        }

    # event handling ----------------------------------------------------------------
    def handle_key_event(self, kind: str, key_id: str) -> dict:
        pressed = kind == "press"
        self.key_state[key_id] = pressed
        key_cfg = self.key_lookup.get(key_id)
        if not key_cfg:
            LOGGER.warning("unknown key id %s", key_id)
            return {
                "type": "key",
                "kind": kind,
                "id": key_id,
                "note": None,
                "freq": None,
                "label": key_id,
            }
        if pressed:
            info = self.synth.note_on(key_id, key_cfg.note)
            freq = info.get("frequency")
        else:
            self.synth.note_off(key_id)
            try:
                freq = note_to_frequency(key_cfg.note, self.live_settings.get("transpose", 0))
            except ValueError:
                freq = None
        return {
            "type": "key",
            "kind": kind,
            "id": key_id,
            "note": key_cfg.note,
            "freq": freq,
            "label": key_cfg.label or key_id,
        }

    def handle_encoder_event(self, name: str, delta: int) -> dict:
        enc_cfg = self.encoder_lookup.get(name)
        if not enc_cfg:
            LOGGER.warning("unknown encoder %s", name)
            return {"type": "enc", "name": name, "value": None, "delta": delta}
        action = enc_cfg.action
        value = None
        if action == "transpose":
            step = int(enc_cfg.step or 1)
            transpose = int(self.live_settings.get("transpose", 0)) + (delta * step)
            transpose = max(-24, min(24, transpose))
            self.live_settings["transpose"] = transpose
            self.synth.set_transpose(transpose)
            value = transpose
        elif action == "volume":
            step = enc_cfg.step or 0.05
            volume = float(self.live_settings.get("volume", 0.7)) + (delta * step)
            volume = max(0.0, min(1.0, volume))
            self.live_settings["volume"] = volume
            self.synth.set_volume(volume)
            value = volume
        elif action == "waveform":
            current = self.live_settings.get("waveform", "sine")
            try:
                idx = SUPPORTED_WAVEFORMS.index(current)
            except ValueError:
                idx = 0
            idx = (idx + delta) % len(SUPPORTED_WAVEFORMS)
            waveform = SUPPORTED_WAVEFORMS[idx]
            self.live_settings["waveform"] = waveform
            self.synth.set_waveform(waveform)
            value = waveform
        else:
            LOGGER.debug("encoder %s has no mapped action", name)
        self.encoder_state[name] = {"action": action, "value": value, "delta": delta}
        return {"type": "enc", "name": name, "action": action, "value": value, "delta": delta}

    # utilities ---------------------------------------------------------------------
    async def test_key(self, key_id: str) -> dict:
        async with self._lock:
            key_cfg = self.key_lookup.get(key_id)
            if not key_cfg:
                raise ValueError(f"unknown key {key_id}")
            info = self.synth.preview(key_cfg.note)
            info.update({"id": key_id, "note": key_cfg.note})
            return info

    async def set_key_note(self, key_id: str, note: str) -> ControllerConfig:
        async with self._lock:
            key_cfg = self.key_lookup.get(key_id)
            if not key_cfg:
                raise ValueError(f"unknown key {key_id}")
            key_cfg.note = note
            payload = self.config.model_dump(mode="python")
            for entry in payload["matrix"]["keys"]:
                if entry["id"] == key_id:
                    entry["note"] = note
            config = self.store.save(payload)
            self._apply_config(config)
            return config

    async def set_encoder_action(self, name: str, action: str) -> ControllerConfig:
        async with self._lock:
            enc_cfg = self.encoder_lookup.get(name)
            if not enc_cfg:
                raise ValueError(f"unknown encoder {name}")
            enc_cfg.action = action
            payload = self.config.model_dump(mode="python")
            for entry in payload["encoders"]:
                if entry["name"] == name:
                    entry["action"] = action
            config = self.store.save(payload)
            self._apply_config(config)
            return config

    async def update_encoder(self, name: str, update_data: dict) -> ControllerConfig:
        async with self._lock:
            enc_cfg = self.encoder_lookup.get(name)
            if not enc_cfg:
                raise ValueError(f"unknown encoder {name}")
            allowed = {"action", "step", "minimum", "maximum"}
            filtered = {k: v for k, v in update_data.items() if k in allowed}
            if not filtered:
                raise ValueError("no encoder fields to update")
            payload = self.config.model_dump(mode="python")
            for entry in payload["encoders"]:
                if entry["name"] == name:
                    entry.update(filtered)
            config = self.store.save(payload)
            self._apply_config(config)
            return config

    async def update_synth_settings(self, update_data: dict) -> ControllerConfig:
        async with self._lock:
            allowed = {"waveform", "volume", "transpose", "attack_ms", "release_ms"}
            filtered = {k: v for k, v in update_data.items() if k in allowed}
            if not filtered:
                raise ValueError("no synth fields to update")
            payload = self.config.model_dump(mode="python")
            payload.setdefault("synth", {}).update(filtered)
            config = self.store.save(payload)
            self._apply_config(config)
            return config
