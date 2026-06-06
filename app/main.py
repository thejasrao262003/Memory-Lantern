"""Memory Lantern — Gradio application entrypoint.

Lays out the three-tab interface and wires up shared session state. Button
callbacks are intentionally left unwired at this stage (see ``# TODO: wire
callback``); this module is the navigable UI shell. Inference happens on Modal
(see ``app/pipeline`` and ``modal_backends``).
"""

from __future__ import annotations

import functools
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

from app import ui_logic
from app.pipeline import orchestrator
from app.tabs import feedback_tab, setup_tab, story_tab

logger = logging.getLogger("memory_lantern")
logging.basicConfig(level=logging.INFO)

# All environment variables the app needs in production (see docs/ERRORS.md).
_REQUIRED_ENV = ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "SUPABASE_URL", "SUPABASE_KEY")

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
        "pending_reactions": {},     # {scene_number(str): reaction} awaiting save
        "adaptation_weights": {},    # dict[str, float]
        "generation_count": 0,       # times generated this session
    }


def _load_css() -> str:
    """Read the custom stylesheet, or return an empty string if unavailable."""
    try:
        return _CSS_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def _run_generation(photos, person_name, event, memory_text, state, progress):
    """Shared logic for Generate and Regenerate.

    Returns a 7-tuple aligned with: (session_state, setup.status, story.gallery,
    story.audio, story.story_html, story.download_button, tabs).
    """
    from pathlib import Path

    error = ui_logic.validate_inputs(photos, person_name, event, memory_text)
    if error:
        return (state, gr.update(value=f"⚠️ {error}", visible=True),
                gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update())

    photo_paths = [Path(getattr(p, "name", p)) for p in (photos or [])]

    def _cb(fraction: float, label: str) -> None:
        try:
            progress(fraction, desc=label)
        except Exception:  # pragma: no cover - progress is best-effort
            pass

    import asyncio

    result = asyncio.run(
        orchestrator.generate_storybook(
            person_name=person_name,
            event=event,
            memory_text=memory_text,
            photos=photo_paths,
            session_id=state.get("session_id", ""),
            progress_callback=_cb,
        )
    )

    # The orchestrator returns a warm error string on failure (never raises).
    if isinstance(result, str):
        return (state, gr.update(value=f"⚠️ {result}", visible=True),
                gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update())

    audio = str(result.audio_path) if result.audio_path else None
    pdf = str(result.pdf_path) if result.pdf_path else None
    new_state = {
        **state,
        "person_name": person_name,
        "event": event,
        "memory_text": memory_text,
        "uploaded_photos": [str(p) for p in photo_paths],
        "scenes": result.scenes,
        "audio_path": audio,
        "pdf_path": pdf,
        "generation_count": state.get("generation_count", 0) + 1,
    }
    # Best-effort: record story metadata (a fast insert). Asset uploads to
    # Supabase Storage are kept out of this hot path to keep the result snappy.
    try:
        from app.storage import session_store

        session_store.save_story_metadata(state.get("session_id", ""), result)
    except Exception:  # noqa: BLE001 - persistence is best-effort (docs/ERRORS.md)
        logger.warning("Could not save story metadata", exc_info=True)

    # Best-effort: upload the narrated video to Supabase for a shareable link.
    video = str(result.video_path) if result.video_path else None
    share_md = ""
    try:
        from app.storage import asset_store, supabase_client

        if supabase_client.is_configured() and result.video_path:
            url = asset_store.save_video(
                state.get("session_id", ""), Path(result.video_path), person_name
            )
            share_md = f"🔗 **Shareable video link:** [{url}]({url})"
    except Exception:  # noqa: BLE001 - sharing is best-effort
        logger.warning("Could not upload video to Supabase", exc_info=True)

    story_html = ui_logic.render_story_html(result.scenes, person_name)
    return (
        new_state,
        gr.update(value="", visible=False),
        gr.update(value=result.images),
        gr.update(value=audio),
        gr.update(value=story_html),
        gr.update(value=pdf),
        gr.update(value=video),
        gr.update(value=share_md, visible=bool(share_md)),
        gr.update(selected="tab_story"),
    )


def handle_generate(photos, person_name, event, memory_text, state, progress=gr.Progress()):
    """Setup-tab Generate callback."""
    return _run_generation(photos, person_name, event, memory_text, state, progress)


def handle_regenerate(state, progress=gr.Progress()):
    """Storybook-tab 'Generate a new version' callback — reuses the saved inputs."""
    return _run_generation(
        state.get("uploaded_photos"),
        state.get("person_name"),
        state.get("event"),
        state.get("memory_text"),
        state,
        progress,
    )


def populate_feedback(state):
    """When the feedback tab opens, show each scene's text above its buttons."""
    scenes = state.get("scenes", []) or []
    updates = []
    for i in range(5):
        text = (scenes[i].get("text") if i < len(scenes) else "") or ""
        body = text.strip() or "_(generate a story first)_"
        updates.append(gr.update(value=f"**Scene {i + 1}**\n\n{body}"))
    return updates


def set_reaction(scene_number, reaction, state):
    """Record a pending reaction for a scene (persisted on Save feedback)."""
    pending = dict(state.get("pending_reactions", {}))
    pending[str(scene_number)] = reaction
    new_state = {**state, "pending_reactions": pending}
    return new_state, gr.update(value=f"Noted — scene {scene_number}: {reaction}.", visible=True)


def save_feedback(notes, state):
    """Persist pending reactions, then refresh the 7-day history table."""
    from app.storage import session_store

    pending = state.get("pending_reactions", {}) or {}
    session_id = state.get("session_id", "")
    saved = 0
    for scene_number, reaction in pending.items():
        try:
            session_store.save_reaction(
                session_id,
                int(scene_number),
                reaction,
                notes if str(scene_number) == "1" else "",
            )
            saved += 1
        except Exception:  # noqa: BLE001 - a failed write is logged, not shown
            logger.warning("Could not save reaction for scene %s", scene_number, exc_info=True)

    history = session_store.load_reaction_history(session_id, days=7)
    rows = [
        [r.get("date"), r.get("scene_number"), r.get("reaction"), r.get("notes", "")]
        for r in history
    ]
    new_state = {**state, "pending_reactions": {}, "reaction_log": history}

    if saved:
        msg = "Thank you — saved. Tomorrow's story will lean into what she loves."
    elif pending:
        msg = "We couldn't save just now. Please try again in a moment."
    else:
        msg = "Tap how each scene felt, then press Save feedback."
    return new_state, gr.update(value=msg, visible=True), gr.update(value=rows)


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
            with gr.Tab("How did it go?", id="tab_feedback") as feedback_tab_handle:
                feedback_components = feedback_tab.build()

        # Wire the Generate / Regenerate flow. Outputs are aligned with the
        # 7-tuple returned by _run_generation.
        generation_outputs = [
            session_state,
            setup_components.status,
            story_components.gallery,
            story_components.audio,
            story_components.story_html,
            story_components.download_button,
            story_components.video,
            story_components.share_link,
            tabs,
        ]
        setup_components.generate_button.click(
            fn=handle_generate,
            inputs=[
                setup_components.photos,
                setup_components.person_name,
                setup_components.event,
                setup_components.written_memory,
                session_state,
            ],
            outputs=generation_outputs,
        )
        story_components.regenerate_button.click(
            fn=handle_regenerate,
            inputs=[session_state],
            outputs=generation_outputs,
        )

        # Feedback tab: show each scene's text when the tab is opened.
        feedback_tab_handle.select(
            fn=populate_feedback,
            inputs=[session_state],
            outputs=feedback_components.scene_texts,
        )
        # Reaction buttons → record a pending reaction for that scene.
        for scene_idx, row in enumerate(feedback_components.reaction_buttons, start=1):
            for reaction_key, button in row:
                button.click(
                    fn=functools.partial(set_reaction, scene_idx, reaction_key),
                    inputs=[session_state],
                    outputs=[session_state, feedback_components.status],
                )
        # Save feedback → persist reactions + refresh the 7-day history.
        feedback_components.save_button.click(
            fn=save_feedback,
            inputs=[feedback_components.notes, session_state],
            outputs=[session_state, feedback_components.status, feedback_components.history],
        )

    return demo


# Module-level app instance so `from app.main import demo` works (HF Spaces and
# tests rely on this).
demo = build_demo()


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
