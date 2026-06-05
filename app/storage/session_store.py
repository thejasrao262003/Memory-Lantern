"""Session store: reaction logs and story metadata in a private HF Dataset.

Records are stored as JSONL — one record per line — partitioned by ``session_id``.
The dataset repo is read from the ``HF_DATASET_REPO`` environment variable and
accessed with ``HF_TOKEN`` via :mod:`huggingface_hub`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.pipeline.orchestrator import StoryResult

DATASET_REPO_ENV = "HF_DATASET_REPO"
HF_TOKEN_ENV = "HF_TOKEN"


def _dataset_repo() -> str:
    """Return the configured dataset repo id or raise if unset."""
    repo = os.environ.get(DATASET_REPO_ENV)
    if not repo:
        raise RuntimeError(
            f"{DATASET_REPO_ENV} is not set; cannot read or write session storage."
        )
    return repo


def save_reaction(
    session_id: str,
    scene_number: int,
    reaction: str,
    notes: str,
) -> None:
    """Append a single reaction record to the session's JSONL partition.

    Args:
        session_id: Stable identifier for this user/session partition.
        scene_number: The 1-indexed scene the reaction is about.
        reaction: One of ``"smiled"``, ``"unsettled"``, ``"asleep"``.
        notes: Free-form caregiver notes (may be empty).

    Raises:
        NotImplementedError: HF Dataset persistence is not wired up yet.
    """
    raise NotImplementedError(
        "Persist reaction to HF Dataset (JSONL append, partitioned by session_id)."
    )


def load_reaction_history(session_id: str, days: int = 7) -> list[dict]:
    """Load reaction records for a session within the last ``days`` days.

    Args:
        session_id: The session partition to read.
        days: Lookback window in days.

    Returns:
        A list of reaction records, newest last.

    Raises:
        NotImplementedError: HF Dataset persistence is not wired up yet.
    """
    raise NotImplementedError(
        "Read reaction history from HF Dataset for the given session and window."
    )


def save_story_metadata(session_id: str, story: "StoryResult") -> None:
    """Persist metadata describing a generated story.

    Stores the scene texts, emotional beats, and asset references (not the raw
    image/audio bytes — those live in :mod:`asset_store`).

    Args:
        session_id: The session partition to write to.
        story: The generated :class:`StoryResult`.

    Raises:
        NotImplementedError: HF Dataset persistence is not wired up yet.
    """
    raise NotImplementedError(
        "Persist story metadata to HF Dataset (JSONL, partitioned by session_id)."
    )
