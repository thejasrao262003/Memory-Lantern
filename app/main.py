"""Memory Lantern — Gradio application entrypoint.

Lays out the three-tab interface and wires up shared session state. Button
callbacks are intentionally left unwired at this stage (see ``# TODO: wire
callback``); this module is the navigable UI shell. Inference happens on Modal
(see ``app/pipeline`` and ``modal_backends``).
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path

# Allow running directly as a script (`python app/main.py`): ensure the project
# root is importable so the `app` package resolves regardless of CWD.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import gradio as gr

try:  # Loading a .env locally is convenient but optional in production.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass

from app.tabs import feedback_tab, setup_tab, story_tab

logger = logging.getLogger("memory_lantern")
logging.basicConfig(level=logging.INFO)

# All environment variables the app needs in production (see docs/ERRORS.md).
_REQUIRED_ENV = ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "HF_TOKEN", "HF_DATASET_REPO")

_CSS_PATH = _PROJECT_ROOT / "app" / "static" / "custom.css"


def check_configuration() -> list[str]:
    """Return the list of required environment variables that are not set."""
    return [name for name in _REQUIRED_ENV if not os.environ.get(name)]


def default_session_state() -> dict:
    """Build a fresh per-session state dict with a unique session id.

    Passed to ``gr.State`` as a callable so each browser session gets its own
    ``session_id`` (see docs/USER_INTERFACE.md and ADR-004).
    """
    return {
        "session_id": str(uuid.uuid4()),
        "person_name": "",
        "event": "",
        "memory_text": "",
        "uploaded_photos": [],       # list of file paths
        "photo_analysis": None,      # PhotoAnalysis or None
        "scenes": [],                # list[SceneDict]
        "images": [],                # list of image paths
        "audio_path": None,          # Path or None
        "pdf_path": None,            # Path or None
        "reaction_log": [],          # list of reaction dicts
        "adaptation_weights": {},    # dict[str, float]
        "generation_count": 0,       # times generated this session
    }


def _load_css() -> str:
    """Read the custom stylesheet, or return an empty string if unavailable."""
    try:
        return _CSS_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def build_demo() -> gr.Blocks:
    """Construct the Gradio Blocks app."""
    missing = check_configuration()
    if missing:
        logger.warning(
            "Missing environment variables: %s. The app will load, but story "
            "generation and storage will not work until these are set as HF "
            "Space secrets.",
            ", ".join(missing),
        )
    else:
        logger.info("Configuration detected (Modal + HF credentials present).")

    with gr.Blocks(
        theme=gr.themes.Soft(),
        title="Memory Lantern",
        css=_load_css(),
    ) as demo:
        gr.Markdown("# 🏮 Memory Lantern")
        gr.Markdown(
            "Turn a family memory and a few photos into a personalised "
            "illustrated storybook — narrated in a warm voice."
        )

        if missing:
            gr.Markdown(
                "⚠️ _The service isn't fully configured yet. "
                "Please contact the administrator._"
            )

        # Shared session state threaded through all three tabs. A callable is
        # passed so each session gets a fresh state (and a unique session_id).
        session_state = gr.State(default_session_state)

        with gr.Tabs() as tabs:
            with gr.Tab("Create a story", id="tab_setup"):
                setup_components = setup_tab.build()
            with gr.Tab("Your storybook", id="tab_story"):
                story_components = story_tab.build()
            with gr.Tab("How did it go?", id="tab_feedback"):
                feedback_components = feedback_tab.build()

        # TODO: wire callback — connect setup_components.generate_button to the
        # orchestrator, stream progress, populate story_components, switch to
        # tab_story, and refresh feedback_components from session_state.
        _ = (setup_components, story_components, feedback_components, session_state, tabs)

    return demo


# Module-level app instance so `from app.main import demo` works (HF Spaces and
# tests rely on this).
demo = build_demo()


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
