"""Narrated MP4 video builder.

Composites the storybook illustrations into a gentle portrait slideshow and lays
the narration WAV over it — one shareable "press play" file. CPU only (no GPU):
each slide's duration is proportional to its scene's text length, so the picture
roughly follows the voice without needing per-scene audio.

Uses the ffmpeg binary bundled by ``imageio-ffmpeg`` (no system ffmpeg needed),
and the stdlib ``wave`` module to read the narration duration.
"""

from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import Image

    from app.pipeline.orchestrator import SceneDict

# Portrait 4:5 — suits the 512x768 illustrations; cream letterbox to match the book.
FRAME_SIZE = (1080, 1350)
BG_COLOR = "0xFDF6EC"
_MIN_SLIDE_SECONDS = 1.5


def _audio_duration_seconds(audio_path: Path) -> float:
    """Read a WAV file's duration via the stdlib (no ffprobe needed)."""
    with wave.open(str(audio_path), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate() or 1
    return frames / float(rate)


def _slide_durations(scenes: "list[SceneDict]", n: int, total: float) -> list[float]:
    """Split ``total`` seconds across ``n`` slides, proportional to text length."""
    texts = [(scenes[i].get("text") if i < len(scenes) else "") or "" for i in range(n)]
    weights = [max(len(t), 1) for t in texts]
    wsum = sum(weights) or n
    return [max(_MIN_SLIDE_SECONDS, total * w / wsum) for w in weights]


def build_video(
    scenes: "list[SceneDict]",
    images: "list[Image.Image]",
    audio_path: Path,
    output_path: Path,
) -> Optional[Path]:
    """Render the narrated slideshow MP4 and return its path.

    Args:
        scenes: The generated scenes (used to weight slide durations).
        images: One illustration per scene, in order.
        audio_path: Path to the narration WAV.
        output_path: Where to write the MP4; parent dirs are created.

    Returns:
        The output path, or ``None`` if there are no images/audio to work with.

    Raises:
        subprocess.CalledProcessError: If ffmpeg fails.
    """
    if not images or not audio_path or not Path(audio_path).exists():
        return None

    from imageio_ffmpeg import get_ffmpeg_exe

    duration = _audio_duration_seconds(Path(audio_path))
    durations = _slide_durations(scenes, len(images), duration)

    work = Path(tempfile.mkdtemp(prefix="ml_video_"))
    list_lines: list[str] = []
    last_png = ""
    for i, (image, secs) in enumerate(zip(images, durations)):
        png = work / f"slide_{i}.png"
        image.convert("RGB").save(png, format="PNG")
        last_png = str(png)
        list_lines.append(f"file '{png}'")
        list_lines.append(f"duration {secs:.3f}")
    # The concat demuxer needs the final image repeated with no duration.
    list_lines.append(f"file '{last_png}'")
    list_file = work / "slides.txt"
    list_file.write_text("\n".join(list_lines), encoding="utf-8")

    w, h = FRAME_SIZE
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={BG_COLOR},"
        "setsar=1,format=yuv420p"
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        get_ffmpeg_exe(),
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-i", str(audio_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "160k",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
