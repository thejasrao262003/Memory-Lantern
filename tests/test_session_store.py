"""Tests for the Supabase-backed session store (client mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.storage import session_store
from app.utils.errors import StorageError


def test_save_reaction_inserts_expected_payload():
    client = MagicMock()
    with patch("app.storage.session_store.get_client", return_value=client):
        session_store.save_reaction("sid-1", 2, "smiled", "she lit up")

    client.table.assert_called_with("reactions")
    payload = client.table.return_value.insert.call_args.args[0]
    assert payload["session_id"] == "sid-1"
    assert payload["scene_number"] == 2
    assert payload["reaction"] == "smiled"
    assert payload["notes"] == "she lit up"
    assert "reaction_date" in payload
    client.table.return_value.insert.return_value.execute.assert_called_once()


def test_save_reaction_rejects_unknown_reaction():
    with patch("app.storage.session_store.get_client") as get_client:
        with pytest.raises(StorageError):
            session_store.save_reaction("sid", 1, "delighted")
        get_client.assert_not_called()  # validated before touching storage


def test_load_reaction_history_normalises_date():
    client = MagicMock()
    chain = (
        client.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value
    )
    chain.execute.return_value = SimpleNamespace(
        data=[{"scene_number": 1, "reaction": "smiled", "reaction_date": "2026-06-05", "notes": ""}]
    )
    with patch("app.storage.session_store.get_client", return_value=client):
        rows = session_store.load_reaction_history("sid", days=7)

    assert len(rows) == 1
    assert rows[0]["date"] == "2026-06-05"  # normalised from reaction_date


def test_load_reaction_history_returns_empty_on_failure():
    with patch("app.storage.session_store.get_client", side_effect=Exception("no db")):
        assert session_store.load_reaction_history("sid") == []


def test_save_story_metadata_inserts_into_stories():
    client = MagicMock()
    story = SimpleNamespace(
        person_name="Margaret",
        scenes=[{"emotional_beat": "joy"}, {"emotional_beat": "pride"}],
        adaptation_weights={"family_relationships": 0.7},
    )
    with patch("app.storage.session_store.get_client", return_value=client):
        session_store.save_story_metadata("sid-1", story)

    client.table.assert_called_with("stories")
    payload = client.table.return_value.insert.call_args.args[0]
    assert payload["person_name"] == "Margaret"
    assert payload["scene_count"] == 2
    assert payload["emotional_beats"] == ["joy", "pride"]
    assert payload["adaptation_weights"] == {"family_relationships": 0.7}
