"""Story generation pipeline step.

Calls the Modal story endpoint (MiniCPM4.1-8B) to turn the photo analysis and
the caregiver's written memory into a five-scene storybook, then enriches each
scene's illustration prompt with era/style modifiers for FLUX.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Optional

from app.pipeline.modal_client import STORY_APP, get_cls
from app.pipeline.photo_analyzer import PhotoAnalysis
from app.utils.errors import ModalEndpointError
from app.utils.prompt_builder import build_illustration_prompt

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.pipeline.orchestrator import SceneDict

_REQUIRED_KEYS = ("scene_number", "text", "illustration_prompt", "emotional_beat")


def generate_story(
    photo_analysis: PhotoAnalysis,
    memory_text: str,
    person_name: str,
    event: str,
    adaptation_weights: Optional[dict] = None,
) -> "list[SceneDict]":
    """Generate a five-scene story from the analysed photos and the memory.

    Args:
        photo_analysis: Structured visual context from the vision step.
        memory_text: The caregiver's written memory, in their own words.
        person_name: Name of the person the memory is about.
        event: Short description of the memory's subject.
        adaptation_weights: Optional mapping of theme -> weight in ``[0, 1]``
            used as a *soft* constraint to emphasise comforting themes.

    Returns:
        A list of exactly five scene dicts. Each scene's ``illustration_prompt``
        is enriched with the era and style from ``photo_analysis``.

    Raises:
        PipelineError: If the endpoint call fails or returns an unusable story.
    """
    try:
        generator = get_cls(STORY_APP, "StoryGenerator")()
        scenes = generator.generate.remote(
            photo_analysis=asdict(photo_analysis),
            memory_text=memory_text,
            person_name=person_name,
            event=event,
            adaptation_weights=adaptation_weights,
        )
    except Exception as exc:  # noqa: BLE001 - warm, retryable message
        raise ModalEndpointError(
            "We had trouble writing the story. Please try again — sometimes it "
            "takes a moment to warm up.",
            stage="story_generator",
            original=exc,
        ) from exc

    scenes = _validate(scenes)

    # Enrich each scene's illustration prompt with era/style modifiers for FLUX.
    for scene in scenes:
        scene["illustration_prompt"] = build_illustration_prompt(
            scene, style_period=photo_analysis.style_period, era=photo_analysis.era
        )
    return scenes


def _validate(scenes: object) -> "list[SceneDict]":
    """Ensure we have exactly five well-formed scenes; raise otherwise."""
    if not isinstance(scenes, list) or len(scenes) != 5:
        raise ModalEndpointError(
            "The story came out a little scrambled. Trying again usually fixes this.",
            stage="story_generator",
        )
    for scene in scenes:
        if not isinstance(scene, dict) or not all(k in scene for k in _REQUIRED_KEYS):
            raise ModalEndpointError(
                "The story came out a little scrambled. Trying again usually fixes this.",
                stage="story_generator",
            )
    return scenes  # type: ignore[return-value]
