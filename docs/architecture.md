# Architecture

Memory Lantern is split into a thin orchestration layer (the Gradio app) and a
set of independent GPU inference services (the Modal backends). State lives in a
private Hugging Face Dataset. PDF assembly happens on the CPU alongside the app.

## System diagram

```
                         ┌──────────────────────────────────────────────┐
                         │           Hugging Face Space (CPU)             │
                         │                                                │
   Caregiver ──HTTP──▶   │   Gradio app  (app/main.py)                    │
                         │     ├─ Tab 1: Create a Story  (setup_tab)      │
                         │     ├─ Tab 2: Your Storybook  (story_tab)      │
                         │     └─ Tab 3: How Did It Go?  (feedback_tab)   │
                         │                                                │
                         │   Orchestrator (app/pipeline/orchestrator.py)  │
                         │     calls each step in sequence with progress  │
                         │                                                │
                         │   PDF builder (app/pdf, WeasyPrint, CPU)       │
                         └───────┬───────────────────────────┬───────────┘
                                 │ HTTPS (Modal SDK)          │ huggingface_hub
                                 ▼                            ▼
        ┌────────────────────────────────────────┐   ┌─────────────────────────┐
        │             Modal (GPU)                  │   │  Private HF Dataset      │
        │                                          │   │  (key-value / JSONL)     │
        │  vision        MiniCPM-V 4.6     A10G     │   │   ├─ reaction logs       │
        │  story         MiniCPM4.1-8B     A10G     │   │   ├─ story metadata      │
        │  illustration  FLUX.1-schnell    A100-40  │   │   └─ generated assets    │
        │  tts           VoxCPM2           A10G     │   └─────────────────────────┘
        │  adaptation    MiniCPM5-1B       T4       │
        └──────────────────────────────────────────┘
```

## Generation flow

1. **Setup** — the caregiver uploads photos, names the person, describes the
   event, and writes the memory (Tab 1).
2. **Vision** — `photo_analyzer` sends the (resized, base64) photos to the
   MiniCPM-V endpoint and gets back a structured `PhotoAnalysis`.
3. **Story** — `story_generator` combines the analysis, the written memory, and
   any adaptation weights into a five-scene story via MiniCPM4.1-8B.
4. **Illustration** — `illustrator` renders one watercolour image per scene in
   parallel via FLUX.1-schnell.
5. **Narration** — `narrator` reads the concatenated story aloud via VoxCPM2 and
   saves a WAV.
6. **PDF** — `app/pdf/builder` assembles the illustrated, paginated storybook,
   always closing on the fixed final line over the first photo.

## Feedback & adaptation loop

Caregivers log per-scene reactions (Tab 3). Reactions are stored in the HF
Dataset via `session_store`. The `adapter` step (MiniCPM5-1B) reasons over the
reaction history to produce theme weights, which are fed back into step 3 as
*soft* preferences — gently steering future stories toward comforting themes.

## Why this split

- **Cost** — GPUs only spin up on demand via Modal; the always-on Space is cheap CPU.
- **Isolation** — each model scales, fails, and deploys independently.
- **Privacy** — all state is in one private dataset scoped to the user's account.
