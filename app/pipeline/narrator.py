"""Narration pipeline step.

Calls the Modal TTS endpoint (VoxCPM2) to read the story aloud in a warm,
unhurried voice and saves the result as a WAV file. The narration always ends on
the same hardcoded line as the PDF's final page.

The voice description is HARDCODED and must not be made configurable
(see ``docs/DECISIONS.md`` ADR-007).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from app.pipeline.modal_client import TTS_APP, get_cls
from app.utils.audio_utils import save_wav_bytes
from app.utils.errors import ModalEndpointError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.pipeline.orchestrator import SceneDict

# 🔒 Non-negotiable voice (docs/MODELS.md, docs/DECISIONS.md ADR-007).
DEFAULT_VOICE_DESCRIPTION = (
    "A warm, unhurried voice like a kind grandmother reading a bedtime story, "
    "speaking slowly and clearly, with gentle pauses between sentences."
)

# 🔒 The narration ends on the same line as the PDF's final page (docs/PROMPTS.md).
FINAL_PAGE_TEXT = (
    "{person_name} looked out at everything she had made, and it was good."
)

# Inserted between scene texts so the narration breathes between scenes.
PAUSE_MARKER = " [pause] "


def _build_full_text(scenes: "list[SceneDict]", person_name: str) -> str:
    """Concatenate scene texts and append the hardcoded final-page line."""
    body = PAUSE_MARKER.join(scene["text"] for scene in scenes if scene.get("text"))
    final = FINAL_PAGE_TEXT.format(person_name=person_name)
    return f"{body}{PAUSE_MARKER}{final}" if body else final


def narrate_story(
    scenes: "list[SceneDict]",
    person_name: str,
    voice_description: str = DEFAULT_VOICE_DESCRIPTION,
) -> Path:
    """Narrate the full story and return the path to the saved audio.

    Args:
        scenes: The generated scenes to narrate, in order.
        person_name: Used to render the final-page line at the end of the audio.
        voice_description: Natural-language description of the desired voice.
            Defaults to the non-negotiable warm voice; do not expose to users.

    Returns:
        Path to the saved WAV file.

    Raises:
        PipelineError: If the TTS endpoint call fails. (The orchestrator may
            choose to continue without audio.)
    """
    full_text = _build_full_text(scenes, person_name)
    try:
        narrator = get_cls(TTS_APP, "Narrator")()
        wav_bytes = narrator.narrate.remote(text=full_text, voice_description=voice_description)
    except Exception as exc:  # noqa: BLE001 - warm message; audio is non-critical
        raise ModalEndpointError(
            "The narration couldn't be recorded this time. Your storybook will "
            "still be available as text and PDF.",
            stage="narrator",
            original=exc,
        ) from exc

    output_dir = Path(tempfile.gettempdir()) / "memory_lantern"
    output_path = output_dir / "narration.wav"
    return save_wav_bytes(wav_bytes, output_path)
