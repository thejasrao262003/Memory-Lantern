# ARCHITECTURE.md — System Architecture

## Overview

Memory Lantern is split into two deployment targets that never share a process:

1. **HF Space** — Gradio frontend + orchestration. CPU only. No model weights.
2. **Modal** — Five separate GPU inference endpoints. No Gradio code.

Communication between them is HTTPS POST calls authenticated with Modal tokens
stored as HF Space secrets.

---

## Component diagram (text)

```
User browser
     │
     ▼
┌─────────────────────────────────────────┐
│  HF Space (CPU Basic)                   │
│                                         │
│  app/main.py          gr.Blocks         │
│  app/tabs/            Gradio UI         │
│  app/pipeline/        Orchestrator      │  ──► Modal: vision endpoint
│  app/storage/         HF Datasets       │  ──► Modal: story endpoint
│  app/pdf/             WeasyPrint        │  ──► Modal: illustration endpoint (×5 parallel)
│  app/utils/           Helpers           │  ──► Modal: TTS endpoint
│                                         │  ──► Modal: adaptation endpoint
└─────────────────────────────────────────┘
                                               │
                                               ▼
                                     ┌──────────────────┐
                                     │  HF Datasets     │
                                     │  (private repo)  │
                                     │  reaction logs   │
                                     │  story metadata  │
                                     └──────────────────┘
```

---

## Data flow — one full generation

```
Step 0  User uploads photos + writes memory text
        ↓
Step 1  photo_analyzer.py
        Sends base64-encoded photos to Modal vision endpoint
        Receives: PhotoAnalysis (era, people, locations, emotional_register, style_period)
        Progress: 0% → 15%
        ↓
Step 2  story_generator.py
        Sends: PhotoAnalysis + memory_text + person_name + event + adaptation_weights
        Receives: list[SceneDict] — 5 scenes, each with text + illustration_prompt
        Progress: 15% → 35%
        ↓
Step 3  illustrator.py  (PARALLEL — ThreadPoolExecutor, max_workers=5)
        For each scene: sends illustration_prompt to Modal FLUX endpoint
        Receives: PNG bytes per scene
        Progress: 35% → 75%
        ↓
Step 4  narrator.py
        Sends: concatenated scene text + voice_description to Modal TTS endpoint
        Receives: WAV bytes
        Progress: 75% → 90%
        ↓
Step 5  pdf/builder.py  (CPU, runs on HF Space)
        Assembles scenes + images + audio into WeasyPrint PDF
        Appends hardcoded final page
        Progress: 90% → 100%
        ↓
Step 6  Storage
        Saves StoryResult metadata to HF Datasets
        Returns pdf_path, audio_path, images to Gradio UI
```

---

## Adaptation loop (daily)

```
Previous session ends
        ↓
Caregiver taps reaction per scene (smiled / unsettled / fell asleep)
        ↓
feedback_tab.py saves to session_store.py → HF Datasets
        ↓
Next generation begins
        ↓
adapter.py loads last 7 days of reactions from HF Datasets
        ↓
Sends reaction_log to Modal adaptation endpoint (MiniCPM5-1B)
        ↓
Receives adaptation_weights dict: {"professional_identity": 0.8, "family": 0.6, ...}
        ↓
Passes weights into story_generator.py as soft constraints
        ↓
Story emphasises what the person responds to
```

---

## What lives where — strict rule

| Code type | Lives in | Never in |
|---|---|---|
| Gradio UI components | app/tabs/ | modal_backends/ |
| Orchestration logic | app/pipeline/ | app/tabs/ |
| Modal endpoint classes | modal_backends/ | app/ |
| Prompt templates | app/utils/prompt_builder.py | modal_backends/ |
| PDF assembly | app/pdf/ | modal_backends/ |
| HF Dataset read/write | app/storage/ | modal_backends/ |
| torch / transformers imports | modal_backends/ | app/ |
| GPU-specific code | modal_backends/ | app/ |

This boundary is absolute. The HF Space imports nothing from modal_backends/
except the modal client to call endpoints. It never imports torch.

---

## Session management

Each browser session gets a UUID (`session_id`) stored in `gr.State`.
All HF Datasets records are keyed by this session_id.
There is no user authentication — this is a hackathon demo.
Session IDs are UUID4, generated on app load.

---

## Error boundaries

Each pipeline step wraps its Modal call in try/except.
On error: log to stderr, return a user-facing error string, do not crash Gradio.
See ERRORS.md for the full taxonomy and user-facing message strings.

---

## Secrets and environment

All secrets are injected as HF Space environment variables:

| Secret name | Used by | Purpose |
|---|---|---|
| MODAL_TOKEN_ID | app/pipeline/*.py | Modal endpoint auth |
| MODAL_TOKEN_SECRET | app/pipeline/*.py | Modal endpoint auth |
| HF_TOKEN | app/storage/*.py | HF Datasets read/write |
| HF_DATASET_REPO | app/storage/*.py | e.g. "username/memory-lantern-data" |

Never hardcode secrets. Never commit secrets. Use python-dotenv for local dev.
