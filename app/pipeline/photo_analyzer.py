"""Photo analysis pipeline step.

Calls the Modal vision endpoint (MiniCPM-V 4.6) to extract structured visual
context from the uploaded photos. This context grounds the story generation and
illustration prompts so the storybook resembles the person's real memories.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.pipeline.modal_client import VISION_APP, get_cls
from app.utils.errors import ModalEndpointError, ValidationError
from app.utils.image_utils import encode_base64, load_image

logger = logging.getLogger("memory_lantern")


@dataclass
class PhotoAnalysis:
    """Structured description of the uploaded photos.

    Attributes:
        era: Approximate time period the photos depict, e.g. "late 1950s".
        people_descriptions: One short description per recognised person.
        locations: Places/settings visible across the photos.
        emotional_register: Overall mood, e.g. "joyful and nostalgic".
        key_objects: Salient objects that anchor the memory (a car, a dress...).
        style_period: Visual style cue for illustration, e.g. "1950s Kodachrome".
    """

    era: str = ""
    people_descriptions: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    emotional_register: str = ""
    key_objects: list[str] = field(default_factory=list)
    style_period: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "PhotoAnalysis":
        """Build a PhotoAnalysis from a (possibly partial) endpoint response."""
        data = data or {}

        def _str(key: str) -> str:
            return str(data.get(key, "") or "")

        def _list(key: str) -> list[str]:
            val = data.get(key, [])
            if isinstance(val, str):
                val = [val]
            return [str(v) for v in val] if isinstance(val, list) else []

        return cls(
            era=_str("era"),
            people_descriptions=_list("people_descriptions"),
            locations=_list("locations"),
            emotional_register=_str("emotional_register"),
            key_objects=_list("key_objects"),
            style_period=_str("style_period"),
        )


def analyze_photos(photos: list[Path], person_name: str) -> PhotoAnalysis:
    """Analyse uploaded photos and return structured visual context.

    Args:
        photos: Paths to the uploaded image files.
        person_name: The name of the person the memory is about; used to help
            the vision model focus its descriptions.

    Returns:
        A :class:`PhotoAnalysis` describing era, people, locations, mood,
        key objects, and visual style period.

    Raises:
        ValidationError: If no photos were provided.
        PipelineError: If every photo fails to open, or the endpoint call fails.
    """
    if not photos:
        raise ValidationError("Please upload at least one photo to get started.")

    images_b64: list[str] = []
    for path in photos:
        try:
            images_b64.append(encode_base64(load_image(path)))
        except Exception:  # noqa: BLE001 - skip a single unreadable photo
            logger.warning("Could not read photo: %s", path)
    if not images_b64:
        raise ModalEndpointError(
            "One or more photos couldn't be read. Please try a different "
            "format (JPEG or PNG).",
            stage="photo_analyzer",
        )

    try:
        vision = get_cls(VISION_APP, "MiniCPMVision")()
        result = vision.analyze.remote(images_b64=images_b64, person_name=person_name)
    except Exception as exc:  # noqa: BLE001 - any remote failure → warm message
        raise ModalEndpointError(
            "Something went wrong while looking at the photos. Please try again.",
            stage="photo_analyzer",
            original=exc,
        ) from exc

    return PhotoAnalysis.from_dict(result)
