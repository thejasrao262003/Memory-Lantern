"""Illustration pipeline step.

Calls the Modal illustration endpoint (FLUX.1-schnell + watercolour LoRA) once
per scene, in parallel, to render the storybook artwork. A single failed image
becomes a warm-cream placeholder rather than failing the whole run.
"""

from __future__ import annotations

import io
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from app.pipeline.modal_client import ILLUSTRATION_APP, get_cls

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import Image

    from app.pipeline.orchestrator import SceneDict

logger = logging.getLogger("memory_lantern")

# Storybook page proportions and the warm-cream placeholder colour (docs/PDF.md).
_IMAGE_SIZE = (512, 768)
_CREAM = (253, 246, 236)  # #FDF6EC

# One thread per scene — parallelism is mandatory (docs/DECISIONS.md ADR-005).
_MAX_PARALLEL_ILLUSTRATIONS = 5


def generate_illustrations(
    scenes: "list[SceneDict]",
    style_period: str,
) -> "list[Image.Image]":
    """Render one illustration per scene, in parallel, preserving scene order.

    Args:
        scenes: The generated scenes, each carrying an ``illustration_prompt``.
        style_period: Visual style cue from the photo analysis, applied to all
            scenes for a consistent look.

    Returns:
        A list of PIL images in the same order as ``scenes``. A scene whose
        render fails is replaced with a warm-cream placeholder.
    """
    illustrator = get_cls(ILLUSTRATION_APP, "Illustrator")()

    def _render(scene: "SceneDict") -> "Image.Image":
        return _illustrate_one(illustrator, scene, style_period)

    with ThreadPoolExecutor(max_workers=_MAX_PARALLEL_ILLUSTRATIONS) as executor:
        # executor.map preserves input order in its results.
        return list(executor.map(_render, scenes))


def _illustrate_one(illustrator, scene: "SceneDict", style_period: str) -> "Image.Image":
    """Render a single scene, falling back to a placeholder on any failure."""
    from PIL import Image

    try:
        png_bytes = illustrator.illustrate.remote(
            prompt=scene["illustration_prompt"],
            scene_number=scene["scene_number"],
            style_period=style_period,
        )
        return Image.open(io.BytesIO(png_bytes)).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - never fail the run for one image
        logger.warning(
            "Illustration failed for scene %s: %s", scene.get("scene_number"), exc
        )
        return Image.new("RGB", _IMAGE_SIZE, color=_CREAM)
