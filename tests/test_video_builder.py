"""Tests for the narrated MP4 video builder.

The full render needs the bundled ffmpeg (imageio-ffmpeg); that test is skipped
if it's unavailable. The pure duration logic is tested unconditionally.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest
from PIL import Image

from app.video import builder
from app.pipeline.orchestrator import SceneDict


def _scene(n: int, text: str) -> SceneDict:
    return SceneDict(scene_number=n, text=text, illustration_prompt="", emotional_beat="x")


def _silent_wav(path: Path, seconds: float = 2.0, rate: int = 22050) -> Path:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        for i in range(int(rate * seconds)):
            wav.writeframes(struct.pack("<h", int(800 * math.sin(i * 0.02))))
    return path


def test_slide_durations_are_proportional_and_sum_to_total():
    scenes = [_scene(1, "a" * 10), _scene(2, "a" * 30)]
    durations = builder._slide_durations(scenes, 2, total=8.0)
    assert len(durations) == 2
    assert durations[1] > durations[0]  # longer text → longer slide
    assert abs(sum(durations) - 8.0) < 0.01


def test_slide_durations_enforce_minimum():
    scenes = [_scene(1, "x"), _scene(2, "y")]
    durations = builder._slide_durations(scenes, 2, total=0.1)
    assert all(d >= builder._MIN_SLIDE_SECONDS for d in durations)


def test_audio_duration_seconds(tmp_path: Path):
    wav = _silent_wav(tmp_path / "a.wav", seconds=2.0)
    assert abs(builder._audio_duration_seconds(wav) - 2.0) < 0.05


def test_build_video_none_without_images(tmp_path: Path):
    wav = _silent_wav(tmp_path / "a.wav")
    assert builder.build_video([], [], wav, tmp_path / "out.mp4") is None


def test_build_video_renders_mp4(tmp_path: Path):
    pytest.importorskip("imageio_ffmpeg")
    wav = _silent_wav(tmp_path / "a.wav", seconds=2.0)
    scenes = [_scene(i + 1, "word " * (i + 1)) for i in range(3)]
    images = [Image.new("RGB", (256, 384), color=c) for c in ("red", "green", "blue")]
    out = builder.build_video(scenes, images, wav, tmp_path / "out.mp4")
    assert out is not None
    assert Path(out).exists()
    assert Path(out).stat().st_size > 0
