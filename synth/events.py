from dataclasses import dataclass
from typing import Literal

@dataclass
class KeyEvent:
    kind: Literal["press", "release"]
    key_id: str

@dataclass
class EncoderEvent:
    name: str
    delta: int   # +1/-1

Event = KeyEvent | EncoderEvent