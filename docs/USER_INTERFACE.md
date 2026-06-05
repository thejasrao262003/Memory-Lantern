# USER_INTERFACE.md — Gradio Interface Specification

Do not add, remove, or rename Gradio components without updating this file.
Every component here has a purpose. The UX is designed for family caregivers,
not developers. Clarity and warmth are more important than feature density.

---

## Overall layout

```python
with gr.Blocks(
    theme=gr.themes.Soft(),
    title="Memory Lantern",
    css="app/static/custom.css"
) as demo:
    gr.Markdown("# Memory Lantern")
    gr.Markdown(
        "Turn a family memory and a few photos into a personalised "
        "illustrated storybook — narrated in a warm voice."
    )

    session_state = gr.State(value=default_session_state)

    with gr.Tabs():
        with gr.Tab("Create a story", id="tab_setup"):
            # setup_tab.py
        with gr.Tab("Your storybook", id="tab_story"):
            # story_tab.py
        with gr.Tab("How did it go?", id="tab_feedback"):
            # feedback_tab.py
```

---

## Session state schema

```python
def default_session_state() -> dict:
    return {
        "session_id": str(uuid.uuid4()),
        "person_name": "",
        "event": "",
        "memory_text": "",
        "uploaded_photos": [],       # list of file paths
        "photo_analysis": None,      # PhotoAnalysis dataclass or None
        "scenes": [],                # list[SceneDict]
        "images": [],                # list of PIL.Image paths
        "audio_path": None,          # Path or None
        "pdf_path": None,            # Path or None
        "reaction_log": [],          # list of reaction dicts
        "adaptation_weights": {},    # dict[str, float]
        "generation_count": 0,       # how many times generated this session
    }
```

---

## Tab 1 — Create a story (setup_tab.py)

### Components

```python
# Photo upload
photo_upload = gr.File(
    label="Upload photos of this person",
    file_count="multiple",
    file_types=["image"],
    # Accepts JPEG, PNG, HEIC
)

# Help text below upload
gr.Markdown(
    "_Upload 1-10 photos. Old photos work best — weddings, "
    "workplaces, family gatherings, holidays._"
)

# Person name
person_name_input = gr.Textbox(
    label="Their name",
    placeholder="e.g. Margaret",
    max_lines=1,
)

# Event
event_input = gr.Textbox(
    label="What is this memory about?",
    placeholder="e.g. Buying her first car — or — Her years as a nurse",
    max_lines=1,
)

# Memory text
memory_input = gr.Textbox(
    label="Write the memory in your own words",
    placeholder=(
        "e.g. When she was young, she saved money for nearly three years "
        "to buy her first car. Her mother thought she was wasting her savings, "
        "but when she finally bought it, she couldn't stop smiling..."
    ),
    lines=6,
    max_lines=20,
)

# Help accordion
with gr.Accordion("Tips for writing the memory", open=False):
    gr.Markdown("""
    - Write in the third person ("she", "he", "they") — the storybook converts it automatically
    - Include specific details: names of people, places, objects
    - Include how it felt, not just what happened
    - 3-5 sentences is ideal. Longer is fine.
    - You don't need to be a good writer — just tell it naturally
    """)

# Generate button
generate_btn = gr.Button(
    "Generate storybook",
    variant="primary",
    size="lg",
)

# Progress bar
progress_bar = gr.Progress(track_tqdm=True)

# Status text
status_text = gr.Markdown(
    "",
    visible=False,  # shown during generation
)
```

### Button callback

```python
generate_btn.click(
    fn=handle_generate,
    inputs=[photo_upload, person_name_input, event_input, memory_input, session_state],
    outputs=[session_state, status_text],
    show_progress=True,
).then(
    fn=lambda: gr.Tabs(selected="tab_story"),
    outputs=[tabs],
)
```

### Validation before generation

```python
def validate_inputs(photos, person_name, event, memory_text) -> str | None:
    """Returns error message string or None if valid."""
    if not photos:
        return "Please upload at least one photo."
    if not person_name.strip():
        return "Please enter their name."
    if not event.strip():
        return "Please describe what this memory is about."
    if len(memory_text.strip()) < 30:
        return "Please write a little more about this memory (at least a sentence or two)."
    return None
```

---

## Tab 2 — Your storybook (story_tab.py)

### Components

```python
# Status message when no story exists
empty_state = gr.Markdown(
    "Your storybook will appear here after you click Generate.",
    visible=True,
)

# Storybook content (hidden until generation complete)
with gr.Column(visible=False) as story_content:

    # Person name heading
    story_title = gr.Markdown("")  # Updated dynamically: "# Margaret's Story"

    # Story scenes — rendered as styled HTML
    story_html = gr.HTML("")

    # Illustration gallery
    story_gallery = gr.Gallery(
        label="Illustrations",
        columns=2,
        rows=3,
        height="auto",
        preview=True,
        show_label=False,
    )

    # Audio narration
    story_audio = gr.Audio(
        label="Listen to your storybook",
        autoplay=False,
        show_download_button=True,
    )

    with gr.Row():
        # Download PDF
        download_btn = gr.DownloadButton(
            "Download storybook (PDF)",
            variant="primary",
        )

        # Regenerate
        regenerate_btn = gr.Button(
            "Generate a new version",
            variant="secondary",
        )

    gr.Markdown(
        "_After listening, head to the 'How did it go?' tab to help us "
        "improve tomorrow's story._"
    )
```

### Story HTML template (rendered by Python)

```python
def render_story_html(scenes: list[SceneDict]) -> str:
    """Render scenes as warm styled HTML for the gr.HTML component."""
    html = ""
    for scene in scenes:
        html += f"""
        <div style="
            background: #FDF6EC;
            border-radius: 12px;
            padding: 24px 32px;
            margin: 16px 0;
            font-family: Georgia, serif;
            font-size: 18px;
            line-height: 1.8;
            color: #3D2B1F;
            border-left: 4px solid #C4956A;
        ">
            <p style="margin: 0;">{scene['text']}</p>
        </div>
        """
    # Final page text
    html += f"""
    <div style="
        background: #F5EBD8;
        border-radius: 12px;
        padding: 32px;
        margin: 24px 0;
        text-align: center;
        font-family: Georgia, serif;
        font-size: 20px;
        font-style: italic;
        color: #3D2B1F;
    ">
        <p>{story_person_name} looked out at everything she had made, and it was good.</p>
    </div>
    """
    return html
```

---

## Tab 3 — How did it go? (feedback_tab.py)

### Components

```python
gr.Markdown(
    "After playing the storybook, tell us how she responded to each part. "
    "This helps us make tomorrow's story even better."
)

# Scene feedback — one row per scene
# These are dynamically populated after generation

feedback_container = gr.Column()

# Inside feedback_container, for each scene (rendered dynamically):
# gr.Markdown(f"**Scene {n}:** {scene_text_preview}")
# with gr.Row():
#     btn_smiled = gr.Button("She smiled", variant="secondary", size="sm")
#     btn_unsettled = gr.Button("She seemed unsettled", variant="stop", size="sm")
#     btn_asleep = gr.Button("She fell asleep", variant="secondary", size="sm")

# Free notes
notes_input = gr.Textbox(
    label="Any other notes? (optional)",
    placeholder="e.g. She recognised the photo of the car immediately",
    lines=3,
)

# Save button
save_feedback_btn = gr.Button("Save feedback", variant="primary")

# Confirmation
feedback_saved_msg = gr.Markdown("", visible=False)

# History
gr.Markdown("### Recent reactions")
feedback_history = gr.Dataframe(
    headers=["Date", "Scene", "Reaction", "Notes"],
    datatype=["str", "number", "str", "str"],
    interactive=False,
    wrap=True,
)
```

### Feedback save logic

```python
def handle_save_feedback(scene_reactions: dict, notes: str, session_state: dict):
    """
    scene_reactions: {1: "smiled", 2: "asleep", 3: "unsettled", ...}
    Saves to HF Datasets via session_store.save_reaction()
    """
    for scene_number, reaction in scene_reactions.items():
        session_store.save_reaction(
            session_id=session_state["session_id"],
            scene_number=scene_number,
            reaction=reaction,
            notes=notes if scene_number == 1 else "",  # notes on first scene only
        )
```

---

## UX copy guidelines

These rules apply to ALL text in the Gradio interface.

1. **Never use clinical or technical language.** No "model", "inference", "generation".
   Use: "creating", "building", "making".

2. **Never mention dementia or Alzheimer's in the UI.** The framing is always positive:
   "preserve memories", "celebrate a life", "share stories".

3. **Always address the family member, not the person with dementia.**
   "Help us improve tomorrow's story for her" — not "the patient's responses".

4. **Error messages are warm, not technical.**
   "Something went wrong — please try again in a moment" — not "Modal endpoint timeout".

5. **Loading states are descriptive and gentle.**
   - 15%: "Looking at the photos..."
   - 35%: "Writing the story..."
   - 75%: "Painting the illustrations..."
   - 90%: "Recording the narration..."
   - 100%: "Your storybook is ready."

6. **Button labels are verbs, not nouns.**
   "Generate storybook" not "Story Generation"
   "Save feedback" not "Submit"
   "Listen" not "Audio"

---

## Custom CSS

File: `app/static/custom.css`

```css
/* Warm cream background for the whole app */
.gradio-container {
    background-color: #FDFAF5 !important;
}

/* Soften the default Gradio tab border */
.tab-nav {
    border-bottom: 2px solid #C4956A !important;
}

/* Warm accent on the primary button */
.primary-button {
    background-color: #A0522D !important;
}

/* Gallery images — soft rounded corners */
.gallery img {
    border-radius: 8px;
}
```
