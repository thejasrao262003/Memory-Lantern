"""Session store: reaction logs and story metadata in Supabase Postgres.

Two tables (schema in docs/STORAGE.md): ``reactions`` and ``stories``, keyed by
an anonymous ``session_id`` UUID.

Reads (:func:`load_reaction_history`) never raise — they return ``[]`` on any
problem, so an unconfigured/empty database simply means "no history". Writes
raise :class:`StorageError` on misconfiguration; callers treat persistence as
best-effort (docs/ERRORS.md: a failed write is logged, never shown to the user).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from app.storage.supabase_client import get_client
from app.utils.errors import StorageError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.pipeline.orchestrator import StoryResult

logger = logging.getLogger("memory_lantern")

REACTIONS_TABLE = "reactions"
STORIES_TABLE = "stories"

VALID_REACTIONS = ("smiled", "unsettled", "asleep")


def save_reaction(
    session_id: str,
    scene_number: int,
    reaction: str,
    notes: str = "",
) -> None:
    """Insert one reaction record.

    Args:
        session_id: Stable identifier for this session partition.
        scene_number: The 1-indexed scene the reaction is about.
        reaction: One of ``"smiled"``, ``"unsettled"``, ``"asleep"``.
        notes: Free-form caregiver notes (may be empty).

    Raises:
        StorageError: If storage is unconfigured or the reaction is invalid.
    """
    if reaction not in VALID_REACTIONS:
        raise StorageError(f"Unknown reaction {reaction!r}.")
    client = get_client()
    client.table(REACTIONS_TABLE).insert(
        {
            "session_id": session_id,
            "scene_number": int(scene_number),
            "reaction": reaction,
            "notes": notes,
            "reaction_date": datetime.now(timezone.utc).date().isoformat(),
        }
    ).execute()


def load_reaction_history(session_id: str, days: int = 7) -> list[dict]:
    """Load this session's reactions from the last ``days`` days (oldest first).

    Never raises — returns ``[]`` if storage is unavailable or empty. Each record
    is normalised to include a ``date`` key (from ``reaction_date``) for the
    adaptation prompt and the history table.
    """
    try:
        client = get_client()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        resp = (
            client.table(REACTIONS_TABLE)
            .select("*")
            .eq("session_id", session_id)
            .gte("reaction_date", cutoff)
            .order("created_at")
            .execute()
        )
        rows = resp.data or []
    except StorageError:
        return []
    except Exception:  # noqa: BLE001 - storage is best-effort on read
        logger.warning("Could not read reaction history", exc_info=True)
        return []

    for row in rows:
        row.setdefault("date", row.get("reaction_date"))
    return rows


def save_story_metadata(
    session_id: str,
    story: "StoryResult",
    adaptation_weights: Optional[dict] = None,
) -> None:
    """Insert story metadata (no photos, no full text — see docs/STORAGE.md).

    Raises:
        StorageError: If storage is unconfigured.
    """
    client = get_client()
    client.table(STORIES_TABLE).insert(
        {
            "session_id": session_id,
            "person_name": getattr(story, "person_name", ""),
            "scene_count": len(getattr(story, "scenes", []) or []),
            "emotional_beats": [
                s.get("emotional_beat", "") for s in getattr(story, "scenes", []) or []
            ],
            "adaptation_weights": adaptation_weights
            or getattr(story, "adaptation_weights", {})
            or {},
        }
    ).execute()
