"""PIL image helpers: resize, compress, and base64 encode.

These run on the HF Space CPU and are used to prepare uploaded photos before
sending them to the Modal vision endpoint, and to handle illustrations coming
back from the illustration endpoint.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

# Longest-edge size we send to the vision model. Keeps payloads small while
# preserving enough detail for analysis.
MAX_UPLOAD_EDGE = 1024


def load_image(path: Path | str) -> Image.Image:
    """Open an image from disk as an RGB :class:`PIL.Image.Image`."""
    img = Image.open(path)
    return img.convert("RGB")


def resize_to_max_edge(image: Image.Image, max_edge: int = MAX_UPLOAD_EDGE) -> Image.Image:
    """Downscale ``image`` so its longest edge is at most ``max_edge`` pixels.

    Aspect ratio is preserved. Images already within bounds are returned
    unchanged.
    """
    width, height = image.size
    longest = max(width, height)
    if longest <= max_edge:
        return image
    scale = max_edge / float(longest)
    new_size = (int(width * scale), int(height * scale))
    return image.resize(new_size, Image.LANCZOS)


def compress_to_jpeg_bytes(image: Image.Image, quality: int = 85) -> bytes:
    """Encode ``image`` as JPEG bytes at the given quality."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def encode_base64(image: Image.Image, quality: int = 85) -> str:
    """Resize, JPEG-compress, and base64-encode ``image`` for HTTP transport.

    Returns:
        An ASCII base64 string (no data-URI prefix), suitable for embedding in
        a JSON request body to a Modal endpoint.
    """
    resized = resize_to_max_edge(image)
    jpeg_bytes = compress_to_jpeg_bytes(resized, quality=quality)
    return base64.b64encode(jpeg_bytes).decode("ascii")


def decode_base64(data: str) -> Image.Image:
    """Decode a base64-encoded image string back into a PIL image."""
    raw = base64.b64decode(data)
    return Image.open(io.BytesIO(raw)).convert("RGB")
