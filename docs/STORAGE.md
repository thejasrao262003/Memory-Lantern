# STORAGE.md — Storage and Session Management

> **IMPLEMENTATION UPDATE (supersedes the HF Datasets design below).**
> Storage now uses **Supabase**: Postgres for the `reactions` and `stories`
> tables, and Supabase **Storage** (bucket `Memory-Lantern`) for generated assets.
> The app uses the `supabase-py` client with the **service-role** key.
> - Schema + bucket: [`supabase_schema.sql`](supabase_schema.sql)
> - Env: `SUPABASE_URL`, `SUPABASE_KEY` (service-role) — replaces `HF_TOKEN` /
>   `HF_DATASET_REPO` for storage.
> - Code: `app/storage/supabase_client.py`, `session_store.py`, `asset_store.py`.
> The same module API (`save_reaction`, `load_reaction_history`,
> `save_story_metadata`) is preserved. The JSONL/HF design below is kept for
> historical context (ADR-006) and is no longer the implementation.

## Overview

Memory Lantern uses two storage mechanisms:

1. **HF Datasets (private repo)** — persistent cross-session storage for
   reaction logs and story metadata. Survives Space restarts.

2. **Gradio gr.State** — in-memory session state for the current browser session.
   Lost on page refresh.

3. **Temp files (HF Space /tmp)** — generated images, audio, PDF during a session.
   Cleared by Space automatically.

---

## HF Dataset repo structure

Repo: set via `HF_DATASET_REPO` environment variable.
Example: `"username/memory-lantern-data"`
Visibility: Private (always — contains personal family data)

```
memory-lantern-data/
├── reactions/
│   └── reactions.jsonl         # Append-only reaction log
├── stories/
│   └── stories.jsonl           # Story metadata log
└── README.md
```

---

## Reactions schema (reactions/reactions.jsonl)

One JSON object per line. Append-only.

```json
{
  "session_id": "uuid4-string",
  "date": "2026-06-10",
  "scene_number": 3,
  "reaction": "smiled",
  "notes": "She recognised the photo of the car immediately",
  "timestamp": "2026-06-10T14:32:00Z"
}
```

**Reaction values:** `"smiled"` | `"unsettled"` | `"asleep"`

---

## Stories schema (stories/stories.jsonl)

One JSON object per line. Append-only.

```json
{
  "session_id": "uuid4-string",
  "date": "2026-06-10",
  "person_name": "Margaret",
  "event": "Buying her first car",
  "scene_count": 5,
  "emotional_beats": ["anticipation", "triumph", "tenderness", "quiet joy", "pride"],
  "adaptation_weights_used": {
    "professional_identity": 0.85,
    "family_relationships": 0.60
  },
  "generation_number": 3,
  "timestamp": "2026-06-10T14:20:00Z"
}
```

---

## session_store.py API

```python
# app/storage/session_store.py

def save_reaction(
    session_id: str,
    scene_number: int,
    reaction: str,      # "smiled" | "unsettled" | "asleep"
    notes: str = "",
) -> None:
    """Append one reaction record to HF Dataset."""
    ...

def load_reaction_history(
    session_id: str,
    days: int = 7,
) -> list[dict]:
    """
    Load last N days of reactions for this session.
    Returns empty list if no history exists.
    """
    ...

def save_story_metadata(
    session_id: str,
    story: "StoryResult",
    adaptation_weights: dict,
) -> None:
    """Append story metadata to HF Dataset."""
    ...
```

---

## asset_store.py API

Generated files (images, audio, PDF) are stored as temp files
in the HF Space /tmp directory during the session.

```python
# app/storage/asset_store.py

def save_images(images: list[Image.Image], session_id: str) -> list[Path]:
    """Save PIL images to /tmp/{session_id}/images/scene_{n}.png"""
    ...

def save_audio(audio_bytes: bytes, session_id: str) -> Path:
    """Save WAV bytes to /tmp/{session_id}/narration.wav"""
    ...

def save_pdf(pdf_bytes: bytes, session_id: str, person_name: str) -> Path:
    """Save PDF to /tmp/{session_id}/{person_name}_storybook.pdf"""
    ...

def cleanup_session(session_id: str) -> None:
    """Delete all temp files for a session."""
    ...
```

---

## HF Dataset write pattern

Use `huggingface_hub` to append records:

```python
from huggingface_hub import HfApi
import json
import os

def _append_record(repo_id: str, path_in_repo: str, record: dict) -> None:
    """Append a JSON record to a JSONL file in a HF Dataset."""
    api = HfApi(token=os.environ["HF_TOKEN"])

    # Download current file (or start empty)
    try:
        existing = api.hf_hub_download(
            repo_id=repo_id,
            filename=path_in_repo,
            repo_type="dataset",
        )
        with open(existing) as f:
            content = f.read()
    except Exception:
        content = ""

    # Append new record
    content += json.dumps(record) + "\n"

    # Upload
    api.upload_file(
        path_or_fileobj=content.encode(),
        path_in_repo=path_in_repo,
        repo_id=repo_id,
        repo_type="dataset",
    )
```

**Note:** This pattern has a race condition under concurrent writes.
For a hackathon demo with one family using the app, this is acceptable.
A production version would use a proper database.

---

## Privacy considerations

This app processes personal family photos and memories.
These rules are absolute:

1. **Photos are never stored.** They live only in Gradio's temp upload directory
   for the duration of a session and are deleted when the session ends.
   Photos are NOT uploaded to HF Datasets, Modal, or any external service
   beyond the Modal inference call (which processes and discards them).

2. **The reaction log contains no photos.** Only text reactions and notes.

3. **Story metadata contains no photos.** Only the person's name, event name,
   and structural metadata.

4. **The HF Dataset repo must be private.** Check `visibility: private` in
   the repo settings. The app refuses to write to a public dataset.

5. **Session IDs are UUIDs with no PII.** No names, no emails, no identifiers
   beyond the UUID are used as storage keys.
