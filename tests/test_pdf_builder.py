"""Tests for the storybook PDF builder.

The full PDF render requires WeasyPrint's native dependencies; that test is
skipped automatically when they're unavailable. The pure helpers and the
non-negotiable final-line contract are tested unconditionally.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.pdf import builder
from app.pipeline.orchestrator import SceneDict


def _scenes() -> list[SceneDict]:
    return [
        SceneDict(
            scene_number=i + 1,
            text=f"Scene {i + 1}.",
            illustration_prompt="p",
            emotional_beat="warm",
        )
        for i in range(5)
    ]


def _images(n: int = 5) -> list[Image.Image]:
    colors = ["red", "green", "blue", "orange", "purple"]
    return [Image.new("RGB", (64, 64), color=colors[i % len(colors)]) for i in range(n)]


def test_final_line_template_is_fixed():
    line = builder.FINAL_LINE_TEMPLATE.format(person_name="Margaret")
    assert line == "Margaret looked out at everything she had made, and it was good."


def test_image_to_data_uri_returns_png_data_uri():
    uri = builder._image_to_data_uri(Image.new("RGB", (8, 8), "red"))
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > len("data:image/png;base64,")


def test_render_html_contains_scene_text_and_final_line():
    html = builder._render_html(_scenes(), _images(), person_name="Margaret")
    assert "Scene 1." in html
    assert "Margaret looked out at everything she had made, and it was good." in html


def test_build_pdf_writes_file(tmp_path: Path):
    pytest.importorskip("weasyprint")
    output = tmp_path / "storybook.pdf"
    result = builder.build_pdf(
        scenes=_scenes(),
        images=_images(),
        person_name="Margaret",
        output_path=output,
    )
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0
