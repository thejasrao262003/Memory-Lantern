"""Tab 1 — "Create a Story".

Lets a caregiver upload photos, name the person, describe the event, and write
the memory in their own words, then kick off generation.
"""

from __future__ import annotations

from dataclasses import dataclass

import gradio as gr


@dataclass
class SetupComponents:
    """Handles to the components on the setup tab, for callback wiring."""

    photos: gr.File
    person_name: gr.Textbox
    event: gr.Textbox
    written_memory: gr.Textbox
    generate_button: gr.Button


def build() -> SetupComponents:
    """Build the "Create a Story" tab and return its component handles."""
    gr.Markdown(
        "## Create a Story\n"
        "Upload a few photos, tell us a little about the memory, and we'll turn "
        "it into a gentle illustrated storybook."
    )

    # Multiple photos (up to 10). gr.Image only handles a single image, so the
    # multi-upload uploader is gr.File constrained to image types.
    photos = gr.File(
        label="Photos (up to 10)",
        file_count="multiple",
        file_types=["image"],
    )

    person_name = gr.Textbox(
        label="Their name",
        placeholder="e.g. Margaret",
    )
    event = gr.Textbox(
        label="What is this memory about?",
        placeholder="e.g. Buying her first car",
    )
    written_memory = gr.Textbox(
        label="Write the memory in your own words",
        lines=6,
        placeholder="Tell us what happened, who was there, and how it felt…",
    )

    generate_button = gr.Button("Generate storybook", variant="primary")

    # A progress bar is supplied to the generation callback via gr.Progress();
    # included here so the layout reserves space and intent is documented.
    gr.Progress()

    with gr.Accordion("How does this work?", open=False):
        gr.Markdown(
            "We look closely at your photos, write a short five-scene story from "
            "your memory, paint a gentle illustration for each scene, and read it "
            "all aloud in a warm voice. Nothing is shared publicly — everything "
            "stays private to your account."
        )

    # TODO: wire callback — generate_button.click(...) -> orchestrator.generate_storybook
    return SetupComponents(
        photos=photos,
        person_name=person_name,
        event=event,
        written_memory=written_memory,
        generate_button=generate_button,
    )
