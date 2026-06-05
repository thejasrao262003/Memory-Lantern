"""Tests for the pure prompt-construction helpers."""

from __future__ import annotations

from app.pipeline.orchestrator import SceneDict
from app.pipeline.photo_analyzer import PhotoAnalysis
from app.utils import prompt_builder


def _analysis() -> PhotoAnalysis:
    return PhotoAnalysis(
        era="late 1950s",
        people_descriptions=["a young woman in a sundress"],
        locations=["a coastal road"],
        emotional_register="joyful",
        key_objects=["a pale blue car"],
        style_period="1950s Kodachrome",
    )


def test_build_vision_prompt_mentions_person():
    prompt = prompt_builder.build_vision_prompt("Margaret")
    assert "Margaret" in prompt
    assert "JSON" in prompt


def test_build_story_prompt_includes_memory_and_context():
    prompt = prompt_builder.build_story_prompt(
        photo_analysis=_analysis(),
        memory_text="She saved for three years.",
        person_name="Margaret",
        event="Buying her first car",
        adaptation_weights=None,
    )
    assert "Margaret" in prompt
    assert "Buying her first car" in prompt
    assert "She saved for three years." in prompt
    assert "late 1950s" in prompt
    assert "five scenes" in prompt


def test_build_story_prompt_includes_adaptation_emphasis():
    prompt = prompt_builder.build_story_prompt(
        photo_analysis=_analysis(),
        memory_text="A memory.",
        person_name="Margaret",
        event="An event",
        adaptation_weights={"family": 0.9, "adventure": 0.2},
    )
    # Highest-weighted theme should be emphasised first.
    assert "family" in prompt
    assert prompt.index("family") < prompt.index("adventure")


def test_build_illustration_prompt_enriches_with_style():
    scene = SceneDict(
        scene_number=1,
        text="...",
        illustration_prompt="a woman beside a blue car",
        emotional_beat="pride",
    )
    prompt = prompt_builder.build_illustration_prompt(
        scene, style_period="1950s Kodachrome", era="late 1950s"
    )
    assert "a woman beside a blue car" in prompt
    assert "1950s Kodachrome" in prompt
    assert "late 1950s" in prompt
    assert "watercolour" in prompt


def test_build_adaptation_prompt_handles_empty_log():
    prompt = prompt_builder.build_adaptation_prompt([])
    assert "no reactions logged yet" in prompt


def test_build_adaptation_prompt_formats_records():
    log = [
        {"scene_number": 1, "reaction": "smiled", "date": "2026-06-01"},
        {"scene_number": 3, "reaction": "unsettled", "date": "2026-06-02"},
    ]
    prompt = prompt_builder.build_adaptation_prompt(log)
    assert "Scene 1" in prompt
    assert "smiled" in prompt
    assert "unsettled" in prompt
