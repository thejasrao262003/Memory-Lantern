"""Tests for the storybook PDF builder.

The full PDF render requires WeasyPrint's native dependencies; that test is
skipped automatically when they're unavailable. The pure helpers, the fairytale
template content, and the non-negotiable final-line contract are tested
unconditionally.
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


def test_data_uri_png_and_jpeg():
    png = builder._data_uri(Image.new("RGB", (8, 8), "red"), "PNG")
    jpeg = builder._data_uri(Image.new("RGB", (8, 8), "red"), "JPEG")
    assert png.startswith("data:image/png;base64,") and len(png) > 32
    assert jpeg.startswith("data:image/jpeg;base64,") and len(jpeg) > 32


def test_render_html_has_cover_story_and_final_line():
    html = builder._render_html(
        _scenes(),
        _images(),
        person_name="Margaret",
        event="Buying her first car",
        first_photo=Image.new("RGB", (32, 32), "blue"),
    )
    # Story prose, set with a drop cap (first letter split into .dropcap span).
    assert 'class="dropcap">S</span>cene 1.' in html
    assert "Margaret" in html
    assert "Buying her first car" in html
    # The non-negotiable closing line
    assert "Margaret looked out at everything she had made, and it was good." in html
    # Fairytale styling is actually present
    assert "Once upon a time" in html
    assert "Cinzel Decorative" in html


def test_render_html_without_photo_falls_back_to_illustration():
    # No first_photo → final page still gets an image (no blank page).
    html = builder._render_html(_scenes(), _images(), "Margaret", "An event", first_photo=None)
    assert "final-photo" in html
    assert 'src="data:image' in html


def test_build_pdf_writes_file(tmp_path: Path):
    pytest.importorskip("weasyprint")
    output = tmp_path / "storybook.pdf"
    result = builder.build_pdf(
        scenes=_scenes(),
        images=_images(),
        person_name="Margaret",
        event="Buying her first car",
        first_photo=Image.new("RGB", (64, 64), "blue"),
        output_path=output,
    )
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0
