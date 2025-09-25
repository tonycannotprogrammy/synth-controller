from dataclasses import dataclass

@dataclass(frozen=True)
class MatrixPinset:
    rows: dict[str, int]
    cols: dict[str, int]

@dataclass(frozen=True)
class EncoderPin:
    name: str
    A: int
    B: int