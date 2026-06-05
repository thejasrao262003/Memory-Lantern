"""Audio helpers for narration: writing WAV bytes and converting to MP3.

These run on the HF Space CPU and handle the audio returned by the VoxCPM2
narration endpoint.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_SAMPLE_RATE = 24_000


def save_wav_bytes(wav_bytes: bytes, output_path: Path | str) -> Path:
    """Write raw WAV bytes to ``output_path``.

    Args:
        wav_bytes: A complete WAV file as returned by the TTS endpoint.
        output_path: Destination path; parent directories are created.

    Returns:
        The path the audio was written to.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(wav_bytes)
    return output_path


def wav_to_mp3(wav_path: Path | str, mp3_path: Path | str | None = None) -> Path:
    """Convert a WAV file to MP3.

    Args:
        wav_path: Path to the source WAV file.
        mp3_path: Optional destination; defaults to ``wav_path`` with a ``.mp3``
            suffix.

    Returns:
        Path to the written MP3 file.

    Raises:
        NotImplementedError: MP3 transcoding is not wired up yet (requires an
            ffmpeg-backed library such as ``pydub`` or ``soundfile`` + ``lameenc``).
    """
    raise NotImplementedError(
        "MP3 transcoding not implemented; narration is served as WAV for now."
    )


def estimate_duration_seconds(text: str, words_per_minute: float = 110.0) -> float:
    """Estimate narration length for a block of text.

    Uses a slow speaking rate appropriate for the target audience. Useful for
    progress estimates and UI hints before audio is generated.
    """
    word_count = len(text.split())
    if word_count == 0:
        return 0.0
    return (word_count / words_per_minute) * 60.0
