"""Pure UI helpers — input validation and story HTML rendering.

Kept free of Gradio and Modal imports so they're trivially unit-testable. The
Gradio wiring in :mod:`app.main` calls these.
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.pipeline.orchestrator import SceneDict

# Mirrors the PDF/narration closing line (docs/DECISIONS.md ADR-003).
FINAL_LINE_TEMPLATE = "{person_name} looked out at everything she had made, and it was good."

_MIN_MEMORY_CHARS = 30


def validate_inputs(
    photos: Optional[list],
    person_name: Optional[str],
    event: Optional[str],
    memory_text: Optional[str],
) -> Optional[str]:
    """Validate the setup form. Returns a warm error string, or ``None`` if OK."""
    if not photos:
        return "Please upload at least one photo to get started."
    if not (person_name or "").strip():
        return "Please enter their name."
    if not (event or "").strip():
        return "Please describe what this memory is about."
    if len((memory_text or "").strip()) < _MIN_MEMORY_CHARS:
        return "Please write a little more about this memory (a sentence or two)."
    return None


def render_story_html(scenes: "list[SceneDict]", person_name: str) -> str:
    """Render the scenes as warm, storybook-styled HTML cards for the app."""
    cards: list[str] = []
    for scene in scenes:
        text = (scene.get("text") or "").strip()
        if not text:
            continue
        cards.append(
            '<div style="background:#FDF6EC;border-radius:12px;padding:24px 32px;'
            "margin:16px 0;font-family:Georgia,serif;font-size:18px;line-height:1.8;"
            'color:#3D2B1F;border-left:4px solid #C4956A;">'
            f'<p style="margin:0;">{escape(text)}</p></div>'
        )

    final_line = FINAL_LINE_TEMPLATE.format(person_name=escape(person_name or ""))
    cards.append(
        '<div style="background:#F5EBD8;border-radius:12px;padding:32px;margin:24px 0;'
        "text-align:center;font-family:Georgia,serif;font-size:20px;font-style:italic;"
        f'color:#3D2B1F;"><p style="margin:0;">{final_line}</p></div>'
    )
    return "\n".join(cards)
