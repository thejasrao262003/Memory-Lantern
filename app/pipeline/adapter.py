"""Adaptation pipeline step.

Calls the Modal adaptation endpoint (MiniCPM5-1B) to reason over the caregiver's
reaction log and produce theme weights. Those weights are fed back into story
generation as soft constraints so future stories lean toward what brings comfort.
"""

from __future__ import annotations

import logging

from app.pipeline.modal_client import ADAPTATION_APP, get_cls

logger = logging.getLogger("memory_lantern")


def compute_adaptation_weights(reaction_log: list[dict]) -> dict[str, float]:
    """Derive theme weights from a history of caregiver-logged reactions.

    Args:
        reaction_log: A list of records shaped like
            ``{"scene_number": int, "reaction": "smiled"|"unsettled"|"asleep",
            "date": str}``.

    Returns:
        A mapping of theme name to weight in ``[0, 1]`` (e.g. ``professional_identity``,
        ``family_relationships``, ``place_and_home``, ``adventure_travel``,
        ``nature_outdoors``). Returns an empty dict if adaptation is unavailable —
        adaptation is best-effort and must never block generation.
    """
    if not reaction_log:
        return {}
    try:
        adapter = get_cls(ADAPTATION_APP, "Adapter")()
        return adapter.adapt.remote(reaction_log)
    except Exception as exc:  # noqa: BLE001 - best-effort; degrade gracefully
        logger.warning("Adaptation endpoint unavailable, skipping: %s", exc)
        return {}
