"""Asset store: generated images, narration, and PDF in Supabase Storage.

Assets are uploaded under a per-session prefix in the ``storybooks`` bucket and
referenced by public URL. All functions are best-effort: callers keep the local
files for immediate display and use these URLs for persistence/sharing.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.storage.supabase_client import ASSET_BUCKET, get_client

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import Image

logger = logging.getLogger("memory_lantern")


def _upload(path_in_bucket: str, data: bytes, content_type: str) -> str:
    """Upload bytes (upsert) and return the public URL."""
    client = get_client()
    bucket = client.storage.from_(ASSET_BUCKET)
    bucket.upload(
        path=path_in_bucket,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return bucket.get_public_url(path_in_bucket)


def save_images(session_id: str, images: "list[Image.Image]") -> list[str]:
    """Upload illustrations as PNGs; return their public URLs (in order)."""
    urls: list[str] = []
    for i, image in enumerate(images, start=1):
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        urls.append(_upload(f"{session_id}/scene_{i}.png", buf.getvalue(), "image/png"))
    return urls


def save_audio(session_id: str, audio_path: Path) -> str:
    """Upload the narration WAV; return its public URL."""
    data = Path(audio_path).read_bytes()
    return _upload(f"{session_id}/narration.wav", data, "audio/wav")


def save_pdf(session_id: str, pdf_path: Path, person_name: str = "") -> str:
    """Upload the storybook PDF; return its public URL."""
    data = Path(pdf_path).read_bytes()
    safe = (person_name or "storybook").replace("/", "_").strip() or "storybook"
    return _upload(f"{session_id}/{safe}_storybook.pdf", data, "application/pdf")


def save_video(session_id: str, video_path: Path, person_name: str = "") -> str:
    """Upload the narrated MP4; return its public URL (the shareable keepsake)."""
    data = Path(video_path).read_bytes()
    safe = (person_name or "storybook").replace("/", "_").strip() or "storybook"
    return _upload(f"{session_id}/{safe}_storybook.mp4", data, "video/mp4")
