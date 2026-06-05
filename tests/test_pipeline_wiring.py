"""Unit tests for the pure (non-Modal) logic in the wired pipeline steps.

The remote calls themselves are exercised end-to-end on Modal; here we test the
deterministic glue: response parsing, narration assembly, and story validation.
"""

from __future__ import annotations

import pytest

from app.pipeline import narrator, story_generator
from app.pipeline.orchestrator import SceneDict
from app.pipeline.photo_analyzer import PhotoAnalysis
from app.utils.errors import ModalEndpointError


def _scene(n: int) -> SceneDict:
    return SceneDict(
        scene_number=n,
        text=f"Scene {n} text.",
        illustration_prompt="prompt",
        emotional_beat="warm",
    )


# -- PhotoAnalysis.from_dict ------------------------------------------------

def test_photo_analysis_from_dict_full():
    pa = PhotoAnalysis.from_dict(
        {
            "era": "1960s",
            "people_descriptions": ["a young woman", "her mother"],
            "locations": ["a seaside town"],
            "emotional_register": "joyful",
            "key_objects": ["a pale blue car"],
            "style_period": "mid-century warm film tones",
        }
    )
    assert pa.era == "1960s"
    assert pa.people_descriptions == ["a young woman", "her mother"]
    assert pa.key_objects == ["a pale blue car"]


def test_photo_analysis_from_dict_coerces_and_defaults():
    # A string where a list is expected becomes a one-item list; missing keys
    # default to empty; nothing raises.
    pa = PhotoAnalysis.from_dict({"locations": "a kitchen", "era": None})
    assert pa.locations == ["a kitchen"]
    assert pa.era == ""
    assert pa.people_descriptions == []


def test_photo_analysis_from_dict_empty():
    pa = PhotoAnalysis.from_dict({})
    assert pa == PhotoAnalysis()


# -- narrator text assembly -------------------------------------------------

def test_build_full_text_appends_final_line():
    text = narrator._build_full_text([_scene(1), _scene(2)], "Margaret")
    assert "Scene 1 text." in text
    assert narrator.PAUSE_MARKER in text
    assert text.strip().endswith(
        "Margaret looked out at everything she had made, and it was good."
    )


def test_build_full_text_only_final_line_when_no_scenes():
    text = narrator._build_full_text([], "Margaret")
    assert text == "Margaret looked out at everything she had made, and it was good."


# -- story validation -------------------------------------------------------

def test_validate_accepts_five_well_formed_scenes():
    scenes = [_scene(i + 1) for i in range(5)]
    assert story_generator._validate(scenes) is scenes


def test_validate_rejects_wrong_count():
    with pytest.raises(ModalEndpointError):
        story_generator._validate([_scene(1), _scene(2)])


def test_validate_rejects_missing_keys():
    bad = [{"scene_number": i + 1, "text": "x"} for i in range(5)]  # missing keys
    with pytest.raises(ModalEndpointError):
        story_generator._validate(bad)
