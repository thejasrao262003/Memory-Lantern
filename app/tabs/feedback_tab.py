"""Tab 3 — "How Did It Go?".

Lets a caregiver log how their loved one reacted to each scene, jot free-form
notes, and review the last week of reaction history.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import gradio as gr

# Memory Lantern always produces exactly five scenes.
NUM_SCENES = 5

REACTION_BUTTONS = [
    ("smiled", "She smiled 🙂"),
    ("unsettled", "She seemed unsettled 😟"),
    ("asleep", "She fell asleep 😴"),
]


@dataclass
class FeedbackComponents:
    """Handles to the components on the feedback tab, for callback wiring."""

    scene_texts: list = field(default_factory=list)
    # reaction_buttons[scene_index] -> list of (reaction_key, gr.Button)
    reaction_buttons: list = field(default_factory=list)
    notes: gr.Textbox = None
    save_button: gr.Button = None
    history: gr.Dataframe = None


def build() -> FeedbackComponents:
    """Build the "How Did It Go?" tab and return its component handles."""
    gr.Markdown(
        "## How Did It Go?\n"
        "Tell us how each part of the story landed. Over time we'll gently lean "
        "into the moments that bring the most comfort."
    )

    scene_texts: list = []
    reaction_buttons: list = []

    for scene_index in range(NUM_SCENES):
        with gr.Group():
            scene_md = gr.Markdown(f"**Scene {scene_index + 1}**\n\n_(story text will appear here)_")
            scene_texts.append(scene_md)
            with gr.Row():
                row_buttons = []
                for reaction_key, label in REACTION_BUTTONS:
                    btn = gr.Button(label, size="sm")
                    row_buttons.append((reaction_key, btn))
                reaction_buttons.append(row_buttons)

    notes = gr.Textbox(
        label="Anything you'd like to note?",
        lines=3,
        placeholder="e.g. She lit up at the photo of the old house.",
    )
    save_button = gr.Button("Save feedback", variant="primary")

    history = gr.Dataframe(
        headers=["Date", "Scene", "Reaction", "Notes"],
        label="Reactions over the last 7 days",
        interactive=False,
        wrap=True,
    )

    # TODO: wire callback — reaction buttons + save_button -> session_store.save_reaction;
    # populate history from session_store.load_reaction_history(session_id, days=7).
    return FeedbackComponents(
        scene_texts=scene_texts,
        reaction_buttons=reaction_buttons,
        notes=notes,
        save_button=save_button,
        history=history,
    )
