"""Storybook PDF assembly.

Renders the Jinja2 template in ``templates/storybook.html`` to PDF with
WeasyPrint. Images are embedded as base64 data URIs so the PDF is fully
self-contained.

WeasyPrint and Jinja2 are imported lazily inside :func:`build_pdf` so this
module remains importable on systems where WeasyPrint's native dependencies
(Pango, cairo, …) are not installed — for example a bare test runner.
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

# The closing line is intentionally fixed and must always appear on the final
# page over the first uploaded photo. This is a deliberate product decision.
FINAL_LINE_TEMPLATE = "{person_name} looked out at everything she had made, and it was good."


def _image_to_data_uri(image: "Image.Image") -> str:
    """Encode a PIL image as a PNG data URI for embedding in HTML."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _render_html(
    scenes: "list[SceneDict]",
    images: "list[Image.Image]",
    person_name: str,
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
            "image_data_uri": _image_to_data_uri(image),
        }
        for scene, image in zip(scenes, images)
    ]

    # The final page always uses the FIRST uploaded photo's illustration slot.
    # In production this is the first uploaded photo; here we use the first
    # rendered image as a stand-in if a dedicated cover photo is not supplied.
    final_image_uri = _image_to_data_uri(images[0]) if images else ""

    return template.render(
        person_name=person_name,
        scenes=scene_blocks,
        final_line=FINAL_LINE_TEMPLATE.format(person_name=person_name),
        final_image_data_uri=final_image_uri,
    )


def build_pdf(
    scenes: "list[SceneDict]",
    images: "list[Image.Image]",
    person_name: str,
    output_path: Path,
    cover_photo: Optional["Image.Image"] = None,
) -> Path:
    """Assemble the storybook PDF and write it to ``output_path``.

    The final page always renders the fixed closing line
    ``"{person_name} looked out at everything she had made, and it was good."``
    over a full-page photo, with no other text. This is non-negotiable.

    Args:
        scenes: The generated scenes.
        images: One illustration per scene, in order.
        person_name: Name used in the closing line.
        output_path: Where to write the PDF; parent dirs are created.
        cover_photo: Optional first uploaded photo to use on the final page. If
            omitted, the first scene illustration is used.

    Returns:
        The path the PDF was written to.

    Raises:
        ImportError: If WeasyPrint is not installed in this environment.
    """
    from weasyprint import HTML

    if cover_photo is not None:
        # Prepend the real cover photo so the final page uses it.
        images = [cover_photo, *images]
        html = _render_html(scenes, images[1:], person_name)
        # Re-render the final image using the cover photo specifically.
        html = html.replace(
            "FINAL_IMAGE_PLACEHOLDER", _image_to_data_uri(cover_photo)
        )
    else:
        html = _render_html(scenes, images, person_name)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(_TEMPLATE_DIR)).write_pdf(str(output_path))
    return output_path
