"""Storybook PDF assembly — a fairytale-styled A5 keepsake.

Layout (see docs/PDF.md): cover → 5 scene pages → final page. The story text on
the scene pages is the same prose that is narrated, set like a printed
children's book (drop caps, ornamental dividers, decorative frames).

The final page ALWAYS shows the first uploaded photo full-bleed with the fixed
closing line — never conditional (docs/DECISIONS.md ADR-003).

WeasyPrint and Jinja2 are imported lazily inside :func:`build_pdf` so this module
stays importable on systems without WeasyPrint's native libraries (e.g. a bare
test runner). Images are embedded as base64 data URIs so the PDF is fully
self-contained.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import Image

    from app.pipeline.orchestrator import SceneDict

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_NAME = "storybook.html"

# The closing line is fixed and must always appear on the final page over the
# first uploaded photo. Deliberate product decision — do not parameterise.
FINAL_LINE_TEMPLATE = "{person_name} looked out at everything she had made, and it was good."


def _data_uri(image: "Image.Image", fmt: str = "PNG") -> str:
    """Encode a PIL image as a base64 data URI (PNG for art, JPEG for photos)."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format=fmt)
    mime = "image/jpeg" if fmt.upper() in ("JPEG", "JPG") else "image/png"
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _render_html(
    scenes: "list[SceneDict]",
    images: "list[Image.Image]",
    person_name: str,
    event: str,
    first_photo: Optional["Image.Image"],
) -> str:
    """Render the storybook HTML from the Jinja2 template."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(_TEMPLATE_NAME)

    scene_blocks = [
        {
            "scene_number": scene["scene_number"],
            "text": scene["text"],
            "image_data_uri": _data_uri(image, "PNG"),
        }
        for scene, image in zip(scenes, images)
    ]

    # Cover vignette: the first illustration if we have one.
    cover_uri = scene_blocks[0]["image_data_uri"] if scene_blocks else ""

    # Final page: the first uploaded photo (JPEG). Fall back to the first
    # illustration only if no photo was supplied, so the page is never blank.
    if first_photo is not None:
        final_uri = _data_uri(first_photo, "JPEG")
    elif images:
        final_uri = _data_uri(images[0], "PNG")
    else:
        final_uri = ""

    return template.render(
        person_name=person_name,
        event=event,
        scenes=scene_blocks,
        cover_image_data_uri=cover_uri,
        final_line=FINAL_LINE_TEMPLATE.format(person_name=person_name),
        final_photo_data_uri=final_uri,
    )


def build_pdf(
    scenes: "list[SceneDict]",
    images: "list[Image.Image]",
    person_name: str,
    event: str,
    first_photo: Optional["Image.Image"],
    output_path: Path,
) -> Path:
    """Assemble the fairytale storybook PDF and write it to ``output_path``.

    Args:
        scenes: The generated scenes (their ``text`` is the printed story).
        images: One illustration per scene, in order.
        person_name: Used on the cover and in the closing line.
        event: Cover subtitle, e.g. "Buying her first car".
        first_photo: The first uploaded photo, shown full-page on the final page.
            If ``None``, the first illustration is used so the page is never blank.
        output_path: Where to write the PDF; parent dirs are created.

    Returns:
        The path the PDF was written to.

    Raises:
        ImportError: If WeasyPrint is not installed in this environment.
    """
    from weasyprint import HTML

    html = _render_html(scenes, images, person_name, event, first_photo)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(_TEMPLATE_DIR)).write_pdf(str(output_path))
    return output_path
