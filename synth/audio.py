from __future__ import annotations

import logging
import math
import threading
from array import array
from typing import Dict, Tuple

try:  # pragma: no cover - optional runtime dependency
    import simpleaudio as sa
except Exception:  # pragma: no cover - optional runtime dependency
    sa = None

LOGGER = logging.getLogger(__name__)
A4_FREQ = 440.0
NOTE_NAMES = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
]
TWO_PI = 2 * math.pi


def note_to_frequency(note: str, transpose: int = 0) -> float:
    """Convert a canonical note name (e.g. C#4) into a frequency."""
    raw = note.strip()
    if len(raw) < 2:
        raise ValueError(f"invalid note '{note}'")
    idx = len(raw) - 1
    digits = []
    while idx >= 0 and (raw[idx].isdigit() or raw[idx] in {"-", "+"}):
        digits.append(raw[idx])
        idx -= 1
    if not digits:
        raise ValueError(f"missing octave in note '{note}'")
    octave = int("".join(reversed(digits)))
    pitch = raw[: idx + 1]
    if pitch not in NOTE_NAMES:
        raise ValueError(f"unknown pitch class '{pitch}'")
    midi_index = NOTE_NAMES.index(pitch) + (octave + 1) * 12
    freq = A4_FREQ * (2 ** ((midi_index + transpose - 69) / 12))
    return float(freq)


class NoteSynth:
    """Lightweight waveform generator that feeds `simpleaudio`."""

    def __init__(
        self,
        sample_rate: int = 44_100,
        voice_duration: float = 3.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.voice_duration = voice_duration
        self.waveform = "sine"
        self.volume = 0.7
        self.transpose = 0
        self.attack_ms = 5
        self.release_ms = 160
        self._cache: Dict[Tuple[str, float, float, int, int], bytes] = {}
        self._playing: Dict[str, "sa.PlayObject"] = {}
        self._key_notes: Dict[str, str] = {}
        self._warned = False

        if sa is None:
            LOGGER.warning(
                "simpleaudio not available – sound playback disabled. Install 'simpleaudio' to enable audio."
            )

    # configuration -----------------------------------------------------------------
    def set_key_notes(self, mapping: Dict[str, str]) -> None:
        self._key_notes = mapping

    def set_waveform(self, waveform: str) -> None:
        if waveform != self.waveform:
            self.waveform = waveform
            self._cache.clear()

    def set_volume(self, volume: float) -> None:
        volume = max(0.0, min(1.0, volume))
        if not math.isclose(volume, self.volume):
            self.volume = volume
            self._cache.clear()

    def set_transpose(self, semitones: int) -> None:
        if semitones != self.transpose:
            self.transpose = semitones

    def set_envelope(self, attack_ms: int, release_ms: int) -> None:
        if attack_ms != self.attack_ms or release_ms != self.release_ms:
            self.attack_ms = attack_ms
            self.release_ms = release_ms
            self._cache.clear()

    # playback ----------------------------------------------------------------------
    def note_on(self, key_id: str, default_note: str | None = None) -> dict:
        note_name = self._key_notes.get(key_id, default_note or "C4")
        try:
            freq = note_to_frequency(note_name, self.transpose)
        except ValueError as err:
            LOGGER.error("cannot play %s: %s", note_name, err)
            return {"note": note_name, "frequency": None}

        if sa is None:
            if not self._warned:
                LOGGER.info("Audio disabled – would play %s (%.2f Hz)", note_name, freq)
                self._warned = True
            return {"note": note_name, "frequency": freq}

        buffer = self._build_buffer(freq)
        try:
            # Stop any currently playing voice for this key for crisp retriggering.
            existing = self._playing.get(key_id)
            if existing:
                existing.stop()
            play_obj = sa.play_buffer(buffer, 1, 2, self.sample_rate)
            self._playing[key_id] = play_obj
        except Exception as err:  # pragma: no cover - sound library runtime
            LOGGER.error("failed to start playback: %s", err)
        return {"note": note_name, "frequency": freq}

    def note_off(self, key_id: str) -> None:
        if sa is None:
            return
        play_obj = self._playing.pop(key_id, None)
        if play_obj:
            try:
                play_obj.stop()
            except Exception as err:  # pragma: no cover
                LOGGER.debug("stopping note failed: %s", err)

    def preview(self, note_name: str) -> dict:
        key_id = f"preview-{note_name}"
        info = self.note_on(key_id, default_note=note_name)
        if sa is not None:
            def _cleanup():
                self._playing.pop(key_id, None)

            timer = threading.Timer(self.voice_duration + 0.1, _cleanup)
            timer.daemon = True
            timer.start()
        return info

    def stop_all(self) -> None:
        if sa is None:
            return
        for play_obj in list(self._playing.values()):
            try:
                play_obj.stop()
            except Exception:  # pragma: no cover
                pass
        self._playing.clear()

    # helpers -----------------------------------------------------------------------
    def _build_buffer(self, freq: float) -> bytes:
        key = (self.waveform, round(freq, 3), self.volume, self.attack_ms, self.release_ms)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        total_samples = int(self.sample_rate * self.voice_duration)
        attack_samples = int(self.sample_rate * self.attack_ms / 1000)
        release_samples = int(self.sample_rate * self.release_ms / 1000)
        data = array("h")

        phase = 0.0
        phase_inc = TWO_PI * freq / self.sample_rate
        for index in range(total_samples):
            sample = self._sample_for_phase(phase)
            amp = self.volume
            if attack_samples and index < attack_samples:
                amp *= index / attack_samples
            elif release_samples and index >= total_samples - release_samples:
                remain = total_samples - index
                amp *= max(0.0, remain / release_samples)
            value = int(max(-1.0, min(1.0, sample)) * amp * 32_767)
            data.append(value)
            phase += phase_inc
            if phase >= TWO_PI:
                phase -= TWO_PI

        buffer = data.tobytes()
        self._cache[key] = buffer
        return buffer

    def _sample_for_phase(self, phase: float) -> float:
        waveform = self.waveform
        if waveform == "sine":
            return math.sin(phase)
        if waveform == "square":
            return 1.0 if math.sin(phase) >= 0 else -1.0
        fraction = phase / TWO_PI
        if waveform == "saw":
            return (2.0 * fraction) - 1.0
        if waveform == "triangle":
            return 2.0 * abs(2.0 * (fraction - math.floor(fraction + 0.5))) - 1.0
        # Fallback to sine if waveform unknown.
        return math.sin(phase)
