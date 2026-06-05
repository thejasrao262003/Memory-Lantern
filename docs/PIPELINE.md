# PIPELINE.md — Inference Pipeline

## Data contracts between stages

This file defines every dataclass and TypedDict that flows between pipeline stages.
Use these exact structures. Do not rename fields without updating all consumers.

---

## Dataclasses (defined in app/pipeline/orchestrator.py)

```python
from dataclasses import dataclass, field
from typing import TypedDict
from pathlib import Path
from PIL import Image


class SceneDict(TypedDict):
    scene_number: int          # 1-5
    text: str                  # Storybook prose, 2-4 sentences
    illustration_prompt: str   # Full enriched FLUX prompt
    emotional_beat: str        # e.g. "quiet pride", "joy", "tenderness"


@dataclass
class PhotoAnalysis:
    era: str                          # e.g. "1960s", "early 1980s"
    people_descriptions: list[str]   # One entry per detected person
    locations: list[str]             # Detected or inferred locations
    emotional_register: str          # Overall emotional tone of the photos
    key_objects: list[str]           # Significant objects (cars, uniforms, etc.)
    style_period: str                # For FLUX: e.g. "mid-century, warm film tones"


@dataclass
class StoryResult:
    scenes: list[SceneDict]
    images: list[Image.Image]        # One per scene, in scene order
    audio_path: Path
    pdf_path: Path
    session_id: str
    person_name: str
    adaptation_weights: dict[str, float] = field(default_factory=dict)
```

---

## Stage 1 — Photo Analysis

**Module:** `app/pipeline/photo_analyzer.py`
**Input:**
- `photos: list[Path]` — local paths to uploaded image files
- `person_name: str`

**Process:**
1. Load and resize each photo to max 1024px on longest side (in `image_utils.py`)
2. Encode to base64
3. POST to Modal vision endpoint
4. Deserialise response into `PhotoAnalysis` dataclass

**Output:** `PhotoAnalysis`

**Error handling:**
- If Modal call fails: raise `PipelineError("Photo analysis failed. Please try again.")`
- If photos list is empty: raise `ValueError("Please upload at least one photo.")`
- If a photo fails to open: skip it, log warning, continue with remaining

---

## Stage 2 — Story Generation

**Module:** `app/pipeline/story_generator.py`
**Input:**
- `photo_analysis: PhotoAnalysis`
- `memory_text: str`
- `person_name: str`
- `event: str`
- `adaptation_weights: dict | None`

**Process:**
1. Build story prompt via `prompt_builder.build_story_prompt()`
2. POST to Modal story endpoint
3. Parse response — model returns JSON array of 5 SceneDict objects
4. Validate: must have exactly 5 scenes, each with required fields
5. Enrich each scene's `illustration_prompt` via `prompt_builder.build_illustration_prompt()`

**Output:** `list[SceneDict]` — exactly 5 items

**Validation:**
```python
assert len(scenes) == 5, f"Expected 5 scenes, got {len(scenes)}"
for scene in scenes:
    assert "scene_number" in scene
    assert "text" in scene
    assert "illustration_prompt" in scene
    assert "emotional_beat" in scene
    assert len(scene["text"]) > 20, "Scene text too short"
```

**Error handling:**
- If model returns malformed JSON: retry once, then raise `PipelineError`
- If scene count != 5: log warning, pad with empty scenes or truncate

---

## Stage 3 — Illustration (Parallel)

**Module:** `app/pipeline/illustrator.py`
**Input:**
- `scenes: list[SceneDict]`
- `style_period: str` (from PhotoAnalysis)

**Process:**
1. For each scene, call Modal illustration endpoint concurrently
2. Use `ThreadPoolExecutor(max_workers=5)` — one thread per scene
3. Each call returns PNG bytes
4. Convert PNG bytes to `PIL.Image.Image`
5. Return list in scene_number order

**Output:** `list[PIL.Image.Image]` — exactly 5 items, same order as scenes

**Parallelism is mandatory.** Sequential generation of 5 FLUX images takes ~60s.
Parallel generation takes ~12-15s. Do not change this to sequential.

**Error handling:**
- If one illustration fails: generate a solid colour placeholder (warm cream #FDF6EC)
  with the scene text rendered on it. Never fail the whole pipeline for one image.

---

## Stage 4 — Narration

**Module:** `app/pipeline/narrator.py`
**Input:**
- `scenes: list[SceneDict]`
- `voice_description: str` (hardcoded — see MODELS.md)

**Process:**
1. Concatenate scene texts with a pause marker between each:
   `full_text = " [pause] ".join(scene["text"] for scene in scenes)`
2. Append final page text:
   `full_text += f" [pause] {person_name} looked out at everything she had made, and it was good."`
3. POST to Modal TTS endpoint
4. Save WAV bytes to temp file
5. Return path

**Output:** `Path` — path to WAV file

**Voice specification (HARDCODED — DO NOT MAKE CONFIGURABLE):**
```
"A warm, unhurried voice like a kind grandmother reading a bedtime story,
speaking slowly and clearly, with gentle pauses between sentences."
```

---

## Stage 5 — PDF Assembly

**Module:** `app/pdf/builder.py`
**Input:**
- `scenes: list[SceneDict]`
- `images: list[PIL.Image.Image]`
- `person_name: str`
- `first_photo: PIL.Image.Image` (the first uploaded photo — for final page)
- `output_path: Path`

**Process:**
1. Save each PIL image to temp PNG
2. Render `app/pdf/templates/storybook.html` via Jinja2
3. Convert to PDF via WeasyPrint
4. Return output_path

**Output:** `Path` — path to PDF file

**Final page rule (HARDCODED — DO NOT REMOVE):**
The Jinja2 template always appends a final page after scene 5:
- `person_name`'s first uploaded photo, filling the full page
- Single line at bottom: `"[person_name] looked out at everything she had made, and it was good."`
- Italic, centred, no other text on the page
- Page break before this page

---

## Orchestrator

**Module:** `app/pipeline/orchestrator.py`

```python
async def generate_storybook(
    person_name: str,
    event: str,
    memory_text: str,
    photos: list[Path],
    session_id: str,
    progress: gr.Progress,
) -> StoryResult:
    """
    Runs all 5 pipeline stages in sequence.
    Updates Gradio progress bar throughout.
    Returns StoryResult or raises PipelineError.
    """
```

**Progress reporting:**

| Stage | Progress % |
|---|---|
| Starting | 0% |
| Vision complete | 15% |
| Story complete | 35% |
| Illustrations complete (all 5) | 75% |
| Narration complete | 90% |
| PDF complete | 100% |

**Adaptation weights:**
Before calling story_generator, the orchestrator checks if a reaction log
exists for this session_id via `session_store.load_reaction_history()`.
If yes, calls `adapter.compute_adaptation_weights()` and passes the result
into `story_generator.generate()`. If no history exists, passes `None`.

---

## Error taxonomy

See ERRORS.md for the full list. Pipeline raises only `PipelineError` or
`ValueError`. Gradio catches these and displays user-friendly messages.
