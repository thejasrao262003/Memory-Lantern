"""Thin helper for calling the deployed Modal inference endpoints.

``modal`` is imported lazily so the rest of the app (and the test suite) stays
importable on machines without Modal installed. The HF Space has ``modal`` in
``requirements.txt`` and reaches the endpoints with the ``MODAL_TOKEN_ID`` /
``MODAL_TOKEN_SECRET`` credentials in its environment.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

# App names must match the ``modal.App(...)`` names in modal_backends/*.py.
VISION_APP = "memory-lantern-vision"
STORY_APP = "memory-lantern-story"
ILLUSTRATION_APP = "memory-lantern-illustration"
TTS_APP = "memory-lantern-tts"
ADAPTATION_APP = "memory-lantern-adaptation"


@lru_cache(maxsize=None)
def get_cls(app_name: str, class_name: str) -> Any:
    """Resolve a deployed Modal class by app + class name (cached).

    Args:
        app_name: The deployed Modal app name, e.g. ``"memory-lantern-vision"``.
        class_name: The ``@app.cls`` class name, e.g. ``"MiniCPMVision"``.

    Returns:
        A ``modal.Cls`` handle. Instantiate it and call ``.method.remote(...)``.

    Raises:
        ImportError: If ``modal`` is not installed in this environment.
    """
    import modal

    return modal.Cls.from_name(app_name, class_name)
