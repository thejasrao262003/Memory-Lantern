# ERRORS.md — Error Handling

## Principles

1. Users of this app are family caregivers, not developers.
   Error messages must be warm and actionable, never technical.

2. Pipeline errors must never crash the Gradio app.
   Every error is caught, logged to stderr, and shown as a user message.

3. Partial failures should not fail the whole pipeline where possible.
   (e.g. one illustration failing should not block PDF generation)

---

## Exception hierarchy

```python
# app/utils/errors.py

class MemoryLanternError(Exception):
    """Base exception. All custom exceptions inherit from this."""
    pass

class PipelineError(MemoryLanternError):
    """Raised when a pipeline stage fails. Contains user-facing message."""
    def __init__(self, user_message: str, stage: str, original: Exception | None = None):
        self.user_message = user_message
        self.stage = stage
        self.original = original
        super().__init__(user_message)

class ValidationError(MemoryLanternError):
    """Raised when user input fails validation."""
    pass

class StorageError(MemoryLanternError):
    """Raised when HF Dataset read/write fails."""
    pass

class ModalEndpointError(PipelineError):
    """Raised when a Modal endpoint call fails."""
    pass
```

---

## Error taxonomy and user-facing messages

| Error condition | User-facing message | Stage |
|---|---|---|
| No photos uploaded | "Please upload at least one photo to get started." | validation |
| Photos fail to open | "One or more photos couldn't be read. Please try a different format (JPEG or PNG)." | photo_analyzer |
| Vision endpoint timeout | "We're taking a little longer than usual to look at the photos. Please try again in a moment." | photo_analyzer |
| Vision endpoint down | "Something went wrong while looking at the photos. Please try again." | photo_analyzer |
| Story generation fails | "We had trouble writing the story. Please try again — sometimes it takes a moment to warm up." | story_generator |
| Story returns bad JSON | "The story came out a little scrambled. Trying again usually fixes this." | story_generator |
| All illustrations fail | "We couldn't create the illustrations this time. Please try again." | illustrator |
| Some illustrations fail | Silent — replace with cream placeholder. Log warning. | illustrator |
| TTS fails | "The narration couldn't be recorded this time. Your storybook will still be available as text and PDF." | narrator |
| PDF generation fails | "We couldn't create the PDF this time. You can still view and listen to the story above." | pdf_builder |
| Modal not configured | "The service isn't configured yet. Please contact the administrator." | startup |
| HF Dataset write fails | Silent — log warning. Reaction is lost but UI shows success. | storage |
| Session has no photos | "Please go back to the first tab and upload some photos." | story_tab |

---

## How errors are displayed in Gradio

```python
# app/pipeline/orchestrator.py

async def generate_storybook(...) -> StoryResult | str:
    """Returns StoryResult on success, or error string on failure."""
    try:
        # ... pipeline stages
    except ValidationError as e:
        return str(e)
    except PipelineError as e:
        import traceback
        traceback.print_exc()  # Log full trace to stderr
        return e.user_message
    except Exception as e:
        import traceback
        traceback.print_exc()
        return "Something unexpected went wrong. Please try again."
```

```python
# app/tabs/setup_tab.py — in button callback

def handle_generate(photos, person_name, event, memory_text, state):
    result = orchestrator.generate_storybook(...)
    if isinstance(result, str):
        # It's an error message
        return state, gr.Markdown(f"⚠️ {result}", visible=True)
    # Success
    state["scenes"] = result.scenes
    # ...
    return state, gr.Markdown("", visible=False)
```

---

## Illustration partial failure handling

If one illustration fails, do not fail the whole generation:

```python
def generate_illustrations(scenes, style_period):
    results = []
    for scene in scenes:
        try:
            png_bytes = Illustrator().illustrate.remote(...)
            results.append(Image.open(io.BytesIO(png_bytes)))
        except Exception as e:
            print(f"WARNING: Illustration failed for scene {scene['scene_number']}: {e}")
            # Generate cream placeholder with scene number
            placeholder = Image.new("RGB", (512, 768), color=(253, 246, 236))
            results.append(placeholder)
    return results
```

---

## Startup validation

On app startup in `app/main.py`, validate that required env vars are set:

```python
def check_configuration() -> list[str]:
    """Returns list of missing configuration items."""
    missing = []
    required = ["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "HF_TOKEN", "HF_DATASET_REPO"]
    for var in required:
        if not os.environ.get(var):
            missing.append(var)
    return missing

# In demo.load():
missing = check_configuration()
if missing:
    print(f"WARNING: Missing environment variables: {missing}")
    # Show banner in UI
```
