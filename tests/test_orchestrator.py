"""Integration tests for the pipeline orchestrator with mocked Modal calls.

The real pipeline steps call Modal GPU endpoints; here every step is patched so
we can verify ordering, error handling, and result assembly without inference.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from app.pipeline.orchestrator import (
    SceneDict,
    StoryResult,
    generate_storybook,
)
from app.pipeline.photo_analyzer import PhotoAnalysis
from app.utils.errors import ModalEndpointError


def _fake_scenes() -> list[SceneDict]:
    return [
        SceneDict(
            scene_number=i + 1,
            text=f"Scene {i + 1} text.",
            illustration_prompt=f"prompt {i + 1}",
            emotional_beat="warm",
        )
        for i in range(5)
    ]


def _run(coro):
    """Run a coroutine to completion on a fresh event loop."""
    return asyncio.run(coro)


def test_generate_storybook_calls_steps_in_order():
    """Each pipeline step runs exactly once, in vision->story->art->tts->pdf order."""
    call_order: list[str] = []

    def fake_analyze(photos, person_name):
        call_order.append("vision")
        return PhotoAnalysis(era="1950s", style_period="Kodachrome")

    def fake_generate(photo_analysis, memory_text, person_name, event, adaptation_weights=None):
        call_order.append("story")
        return _fake_scenes()

    def fake_illustrate(scenes, style_period):
        call_order.append("illustration")
        return ["img1", "img2", "img3", "img4", "img5"]

    def fake_narrate(scenes, *args, **kwargs):
        call_order.append("tts")
        return Path("output/narration.wav")

    def fake_build_pdf(scenes, images, person_name, output_path, **kwargs):
        call_order.append("pdf")
        return Path(output_path)

    with patch("app.pipeline.photo_analyzer.analyze_photos", side_effect=fake_analyze), \
         patch("app.pipeline.story_generator.generate_story", side_effect=fake_generate), \
         patch("app.pipeline.illustrator.generate_illustrations", side_effect=fake_illustrate), \
         patch("app.pipeline.narrator.narrate_story", side_effect=fake_narrate), \
         patch("app.pdf.builder.build_pdf", side_effect=fake_build_pdf):
        result = _run(
            generate_storybook(
                person_name="Margaret",
                event="Buying her first car",
                memory_text="A treasured memory.",
                photos=[Path("tests/fixtures/sample_photo.jpg")],
            )
        )

    assert call_order == ["vision", "story", "illustration", "tts", "pdf"]
    assert isinstance(result, StoryResult)


def test_generate_storybook_populates_result():
    """StoryResult is populated from the (mocked) step outputs."""
    scenes = _fake_scenes()
    audio = Path("output/narration.wav")

    with patch("app.pipeline.photo_analyzer.analyze_photos", return_value=PhotoAnalysis()), \
         patch("app.pipeline.story_generator.generate_story", return_value=scenes), \
         patch("app.pipeline.illustrator.generate_illustrations", return_value=["a", "b"]), \
         patch("app.pipeline.narrator.narrate_story", return_value=audio), \
         patch("app.pdf.builder.build_pdf", side_effect=lambda **kw: kw["output_path"]):
        result = _run(
            generate_storybook(
                person_name="Margaret",
                event="Buying her first car",
                memory_text="A treasured memory.",
                photos=[Path("p.jpg")],
            )
        )

    assert result.scenes == scenes
    assert result.images == ["a", "b"]
    assert result.audio_path == audio
    assert result.pdf_path is not None


def test_illustration_error_returns_user_facing_message():
    """A PipelineError in a stage is returned as its warm, user-facing message."""
    message = "The illustrator endpoint is unavailable."
    with patch("app.pipeline.photo_analyzer.analyze_photos", return_value=PhotoAnalysis()), \
         patch("app.pipeline.story_generator.generate_story", return_value=_fake_scenes()), \
         patch(
             "app.pipeline.illustrator.generate_illustrations",
             side_effect=ModalEndpointError(message, stage="illustrator"),
         ):
        result = _run(
            generate_storybook(
                person_name="Margaret",
                event="Buying her first car",
                memory_text="A treasured memory.",
                photos=[Path("p.jpg")],
            )
        )

    # The orchestrator never throws into Gradio — it returns the message string.
    assert result == message


def test_generic_failure_returns_friendly_string():
    """An unexpected error becomes a friendly fallback string, not an exception."""
    with patch("app.pipeline.photo_analyzer.analyze_photos", side_effect=RuntimeError("boom")):
        result = _run(
            generate_storybook(
                person_name="Margaret",
                event="Buying her first car",
                memory_text="A treasured memory.",
                photos=[Path("p.jpg")],
            )
        )

    assert isinstance(result, str)
    assert "went wrong" in result.lower()
