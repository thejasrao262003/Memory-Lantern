"""Tab 2 — "Your Storybook".

Displays the generated illustrations, narration, story text, and a PDF download.
"""

from __future__ import annotations

from dataclasses import dataclass

import gradio as gr


@dataclass
class StoryComponents:
    """Handles to the components on the storybook tab, for callback wiring."""

    gallery: gr.Gallery
    audio: gr.Audio
    story_html: gr.HTML
    download_button: gr.DownloadButton
    regenerate_button: gr.Button


def build() -> StoryComponents:
    """Build the "Your Storybook" tab and return its component handles."""
    gr.Markdown("## Your Storybook")

    gallery = gr.Gallery(
        label="Illustrations",
        columns=2,
        preview=True,
        height="auto",
    )

    audio = gr.Audio(
        label="Narration",
        autoplay=False,
        type="filepath",
    )

    story_html = gr.HTML(
        value="<p style='color:#7a7268'>Your story will appear here once it's ready.</p>",
        label="Story",
    )

    with gr.Row():
        download_button = gr.DownloadButton("Download storybook PDF")
        regenerate_button = gr.Button("Generate a new version", variant="secondary")

    # TODO: wire callback — populated by orchestrator output; regenerate_button
    # re-runs generation with the same inputs.
    return StoryComponents(
        gallery=gallery,
        audio=audio,
        story_html=story_html,
        download_button=download_button,
        regenerate_button=regenerate_button,
    )
