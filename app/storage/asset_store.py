"""Asset store: generated images and narration audio in a private HF Dataset.

Binary assets are uploaded under a per-session prefix and referenced by URL/path
from the story metadata kept in :mod:`session_store`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL import Image


def save_images(session_id: str, images: "list[Image.Image]") -> list[str]:
    """Upload generated illustrations and return their stored references.

    Args:
        session_id: Per-session storage prefix.
        images: The rendered illustrations to persist.

    Returns:
        A list of repo-relative paths (or URLs) for the uploaded images, in
        order.

    Raises:
        NotImplementedError: HF Dataset asset upload is not wired up yet.
    """
    raise NotImplementedError("Upload images to HF Dataset under the session prefix.")


def save_audio(session_id: str, audio_path: Path) -> str:
    """Upload the narration audio and return its stored reference.

    Raises:
        NotImplementedError: HF Dataset asset upload is not wired up yet.
    """
    raise NotImplementedError("Upload narration audio to HF Dataset.")


def load_image(reference: str) -> "Image.Image":
    """Download a previously stored image by its reference.

    Raises:
        NotImplementedError: HF Dataset asset download is not wired up yet.
    """
    raise NotImplementedError("Download image from HF Dataset by reference.")


def load_audio(reference: str, destination: Path) -> Path:
    """Download previously stored narration audio to ``destination``.

    Raises:
        NotImplementedError: HF Dataset asset download is not wired up yet.
    """
    raise NotImplementedError("Download narration audio from HF Dataset by reference.")
