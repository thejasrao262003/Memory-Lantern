"""Tests for the pure UI helpers (validation + story HTML rendering)."""

from __future__ import annotations

from app import ui_logic
from app.pipeline.orchestrator import SceneDict


def _scene(n: int, text: str) -> SceneDict:
    return SceneDict(scene_number=n, text=text, illustration_prompt="p", emotional_beat="warm")


# -- validation -------------------------------------------------------------

def test_validate_requires_photos():
    assert ui_logic.validate_inputs([], "Margaret", "Her car", "x" * 40) == (
        "Please upload at least one photo to get started."
    )


def test_validate_requires_name():
    assert "name" in ui_logic.validate_inputs(["p.jpg"], "  ", "Her car", "x" * 40).lower()


def test_validate_requires_event():
    assert "memory is about" in ui_logic.validate_inputs(["p.jpg"], "Margaret", "", "x" * 40)


def test_validate_requires_longer_memory():
    msg = ui_logic.validate_inputs(["p.jpg"], "Margaret", "Her car", "too short")
    assert "a little more" in msg


def test_validate_passes_on_good_input():
    assert ui_logic.validate_inputs(["p.jpg"], "Margaret", "Her car", "x" * 40) is None


# -- story HTML -------------------------------------------------------------

def test_render_story_html_includes_scenes_and_final_line():
    scenes = [_scene(1, "She bought the car."), _scene(2, "She drove to the coast.")]
    html = ui_logic.render_story_html(scenes, "Margaret")
    assert "She bought the car." in html
    assert "She drove to the coast." in html
    assert "Margaret looked out at everything she had made, and it was good." in html


def test_render_story_html_skips_empty_scenes_and_escapes():
    scenes = [_scene(1, ""), _scene(2, "A <tag> & ampersand")]
    html = ui_logic.render_story_html(scenes, "Margaret")
    # Empty scene contributes no card text; HTML is escaped.
    assert "&lt;tag&gt;" in html
    assert "&amp;" in html
