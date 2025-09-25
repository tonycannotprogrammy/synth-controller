from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

NOTE_NAMES = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
]
SUPPORTED_WAVEFORMS = ["sine", "square", "saw", "triangle"]
EncoderAction = Literal["none", "transpose", "volume", "waveform"]


FLAT_TO_SHARP = {
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
}


def _normalise_note(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("note must not be empty")
    head = raw[0].upper()
    remainder = raw[1:]
    accidental = ""
    if remainder:
        first = remainder[0]
        if first in {"#", "♯"}:
            accidental = "#"
            remainder = remainder[1:]
        elif first in {"b", "♭"}:
            accidental = "b"
            remainder = remainder[1:]
    pitch = head + accidental
    pitch = pitch.replace("H", "B")
    pitch_key = pitch if accidental else pitch.upper()
    if pitch_key in FLAT_TO_SHARP:
        pitch = FLAT_TO_SHARP[pitch_key]
    else:
        pitch = pitch.upper()
    if pitch not in NOTE_NAMES:
        raise ValueError(f"unsupported pitch class '{pitch}'")
    if not remainder or not remainder.lstrip("-+").isdigit():
        raise ValueError("octave must be an integer")
    octave = int(remainder)
    if not -1 <= octave <= 8:
        raise ValueError("octave out of supported range (-1..8)")
    return f"{pitch}{octave}"


class KeyConfig(BaseModel):
    id: str
    row: str
    col: str
    note: str = Field(default="C4")
    label: str | None = None

    @field_validator("note")
    @classmethod
    def _validate_note(cls, value: str) -> str:
        return _normalise_note(value)


class EncoderConfig(BaseModel):
    name: str
    A: int
    B: int
    action: EncoderAction = Field(default="none")
    step: float | None = None
    minimum: float | None = None
    maximum: float | None = None

    @field_validator("step")
    @classmethod
    def _validate_step(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("step must be positive")
        return value


class MatrixConfig(BaseModel):
    rows: dict[str, int]
    cols: dict[str, int]
    keys: list[KeyConfig]


class SynthSettings(BaseModel):
    waveform: str = Field(default="sine")
    volume: float = Field(default=0.7, ge=0.0, le=1.0)
    transpose: int = Field(default=0, ge=-24, le=24)
    attack_ms: int = Field(default=5, ge=0, le=500)
    release_ms: int = Field(default=120, ge=10, le=5000)

    @field_validator("waveform")
    @classmethod
    def _validate_waveform(cls, value: str) -> str:
        if value not in SUPPORTED_WAVEFORMS:
            raise ValueError(f"waveform must be one of {', '.join(SUPPORTED_WAVEFORMS)}")
        return value


class AppSettings(BaseModel):
    web_host: str = Field(default="0.0.0.0")
    web_port: int = Field(default=8080)
    debounce_ms: int = Field(default=12, ge=1, le=100)


class ControllerConfig(BaseModel):
    matrix: MatrixConfig
    encoders: list[EncoderConfig]
    synth: SynthSettings = Field(default_factory=SynthSettings)
    app: AppSettings = Field(default_factory=AppSettings)

    def jsonable(self) -> dict:
        return self.model_dump(mode="json")


class ConfigStore:
    """Thread-safe helper around YAML based controller configuration."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = Lock()
        self._cached: ControllerConfig | None = None

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> ControllerConfig:
        with self._lock:
            data = yaml.safe_load(self._path.read_text()) or {}
            config = ControllerConfig.model_validate(data)
            self._cached = config
            return config

    def get_cached(self) -> ControllerConfig:
        if self._cached is None:
            return self.load()
        return self._cached

    def save(self, config: ControllerConfig | dict) -> ControllerConfig:
        with self._lock:
            if isinstance(config, ControllerConfig):
                model = config
            else:
                model = ControllerConfig.model_validate(config)
            self._path.write_text(yaml.safe_dump(model.model_dump(mode="python"), sort_keys=False))
            self._cached = model
            return model

    def update(self, payload: dict) -> ControllerConfig:
        current = self.get_cached()
        merged = current.model_copy(update=payload)
        return self.save(merged)


def default_config(path: Path) -> ControllerConfig:
    template = {
        "matrix": {
            "rows": {"ROW0": 2, "ROW1": 3, "ROW2": 14},
            "cols": {"COL0": 18, "COL1": 6, "COL2": 5, "COL3": 0, "COL4": 11, "COL5": 4},
            "keys": [
                {"id": f"MX{i}", "row": row, "col": col, "note": "C4"}
                for i, (row, col) in enumerate(
                    [
                        ("ROW1", "COL0"), ("ROW1", "COL1"), ("ROW1", "COL2"), ("ROW1", "COL3"),
                        ("ROW1", "COL4"), ("ROW1", "COL5"), ("ROW2", "COL0"), ("ROW2", "COL1"),
                        ("ROW2", "COL2"), ("ROW2", "COL3"), ("ROW2", "COL4"), ("ROW2", "COL5"),
                    ], start=1
                )
            ],
        },
        "encoders": [
            {"name": "SW1", "A": 26, "B": 12, "action": "transpose", "step": 1},
            {"name": "SW2", "A": 19, "B": 1, "action": "volume", "step": 0.05},
            {"name": "SW3", "A": 13, "B": 7, "action": "waveform"},
            {"name": "SW4", "A": 10, "B": 22, "action": "none"},
            {"name": "SW5", "A": 17, "B": 9, "action": "none"},
        ],
        "synth": {
            "waveform": "sine",
            "volume": 0.7,
            "transpose": 0,
            "attack_ms": 5,
            "release_ms": 180,
        },
        "app": {"web_host": "0.0.0.0", "web_port": 8080, "debounce_ms": 12},
    }
    store = ConfigStore(path)
    return store.save(template)
