"""Pipeline orchestrator.

Coordinates the full storybook-generation pipeline by calling each Modal
endpoint in sequence and emitting progress updates. Defines the shared
:class:`StoryResult` dataclass and :class:`SceneDict` TypedDict used across the
pipeline.

Error model (see ``docs/ERRORS.md``): pipeline stages raise
:class:`~app.utils.errors.PipelineError` (or :class:`ValidationError`) with a
warm, user-facing message. :func:`generate_storybook` catches everything, logs
the full trace to stderr, and returns either a :class:`StoryResult` (success) or
a user-facing ``str`` (failure) — it never throws into the Gradio layer.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, TypedDict

from app.pipeline import (
    adapter,
    illustrator,
    narrator,
    photo_analyzer,
    story_generator,
)
from app.storage import session_store
from app.utils.errors import PipelineError, ValidationError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import Image


class SceneDict(TypedDict):
    """A single storybook scene.

    Keys:
        scene_number: 1-indexed position of the scene (1..5).
        text: The narrative prose shown and narrated for this scene.
        illustration_prompt: Enriched FLUX prompt used to render the scene.
        emotional_beat: The emotional intent of the scene, e.g. "quiet pride".
    """

    scene_number: int
    text: str
    illustration_prompt: str
    emotional_beat: str


@dataclass
class StoryResult:
    """The complete output of a storybook generation run.

    Attributes:
        scenes: The five generated scenes.
        images: One rendered illustration per scene, as PIL images.
        audio_path: Path to the narrated WAV file.
        pdf_path: Path to the assembled storybook PDF.
        session_id: The session this story belongs to.
        person_name: Name of the person the memory is about.
        adaptation_weights: Theme weights applied to this generation (empty if none).
    """

    scenes: list[SceneDict] = field(default_factory=list)
    images: "list[Image.Image]" = field(default_factory=list)
    audio_path: Optional[Path] = None
    pdf_path: Optional[Path] = None
    video_path: Optional[Path] = None
    session_id: str = ""
    person_name: str = ""
    adaptation_weights: dict[str, float] = field(default_factory=dict)


# A progress callback receives a fraction in [0, 1] and a human-readable label.
# The Gradio layer adapts ``gr.Progress`` to this signature.
ProgressCallback = Callable[[float, str], None]


def _load_adaptation_weights(session_id: str) -> Optional[dict]:
    """Load reaction history and compute adaptation weights, if any exist.

    Failures here are non-fatal: a missing history, an unconfigured dataset, or
    an adaptation-endpoint hiccup simply means we generate an unadapted story.
    Returns ``None`` when there is nothing to adapt to.
    """
    try:
        history = session_store.load_reaction_history(session_id, days=7)
    except Exception:  # noqa: BLE001 - no history is a normal, silent case
        return None
    if not history:
        return None
    try:
        return adapter.compute_adaptation_weights(history)
    except Exception:  # noqa: BLE001 - adaptation is best-effort
        traceback.print_exc()
        return None


async def generate_storybook(
    person_name: str,
    event: str,
    memory_text: str,
    photos: list[Path],
    session_id: str = "",
    progress_callback: Optional[ProgressCallback] = None,
) -> "StoryResult | str":
    """Run the full pipeline and return an assembled storybook or an error string.

    Steps and their progress checkpoints (see ``docs/PIPELINE.md``):
        * 15%  — analyse photos (vision)
        * 35%  — generate the five-scene story (story)
        * 75%  — render illustrations in parallel (illustration)
        * 88%  — narrate the story (TTS)
        * 95%  — assemble the PDF
        * 100% — composite the narrated MP4 video

    Args:
        person_name: Name of the person the memory is about.
        event: Short description of the memory's subject.
        memory_text: The caregiver's written memory.
        photos: Paths to the uploaded photos.
        session_id: Session/storage partition; used to load reaction history.
        progress_callback: Optional callable invoked with ``(fraction, label)``
            as the pipeline advances.

    Returns:
        A populated :class:`StoryResult` on success, or a warm, user-facing
        error ``str`` on failure. Never raises into the caller.
    """

    def _progress(fraction: float, label: str) -> None:
        if progress_callback is not None:
            progress_callback(fraction, label)

    # Imported lazily to keep the import graph clean and the app importable
    # even when WeasyPrint's native dependencies are unavailable.
    from app.pdf import builder as pdf_builder

    try:
        adaptation_weights = _load_adaptation_weights(session_id)

        _progress(0.15, "Looking at the photos…")
        analysis = photo_analyzer.analyze_photos(photos, person_name)

        _progress(0.35, "Writing the story…")
        scenes = story_generator.generate_story(
            photo_analysis=analysis,
            memory_text=memory_text,
            person_name=person_name,
            event=event,
            adaptation_weights=adaptation_weights,
        )

        _progress(0.75, "Painting the illustrations…")
        images = illustrator.generate_illustrations(scenes, analysis.style_period)

        _progress(0.88, "Recording the narration…")
        audio_path = narrator.narrate_story(scenes, person_name=person_name)

        _progress(0.95, "Binding the storybook…")
        # The final page shows the first uploaded photo; load it on the CPU here.
        first_photo = None
        if photos:
            from app.utils.image_utils import load_image

            try:
                first_photo = load_image(photos[0])
            except Exception:  # noqa: BLE001 - builder falls back to first illustration
                first_photo = None
        pdf_path = pdf_builder.build_pdf(
            scenes=scenes,
            images=images,
            person_name=person_name,
            event=event,
            first_photo=first_photo,
            output_path=Path("output") / f"{person_name}_storybook.pdf",
        )

        _progress(1.00, "Making a shareable video…")
        # The narrated video is a keepsake nicety — never fail the story over it.
        video_path = None
        try:
            from app.video import builder as video_builder

            if audio_path and images:
                video_path = video_builder.build_video(
                    scenes=scenes,
                    images=images,
                    audio_path=audio_path,
                    output_path=Path("output") / f"{person_name}_storybook.mp4",
                )
        except Exception:  # noqa: BLE001 - video is best-effort
            traceback.print_exc()
            video_path = None
    except ValidationError as exc:
        return str(exc)
    except PipelineError as exc:
        traceback.print_exc()
        return exc.user_message
    except Exception:  # noqa: BLE001 - last-resort guard; never crash Gradio
        traceback.print_exc()
        return "Something unexpected went wrong. Please try again."

    return StoryResult(
        scenes=scenes,
        images=images,
        audio_path=audio_path,
        pdf_path=pdf_path,
        video_path=video_path,
        session_id=session_id,
        person_name=person_name,
        adaptation_weights=adaptation_weights or {},
    )
