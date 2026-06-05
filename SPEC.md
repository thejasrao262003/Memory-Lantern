# Memory Lantern — Technical Specification

> **One line:** Turn a family memory and a few photos into a personalised
> illustrated storybook, narrated in a warm voice — built for families caring
> for loved ones with early-stage dementia.

This document is the consolidated, authoritative specification for Memory
Lantern. It synthesises the full `docs/` set into a single reference. Where this
file and a `docs/*` file ever disagree, the detailed `docs/*` file wins — see
the [Source-of-truth map](#source-of-truth-map).

- **Built for:** Gradio × Hugging Face "Build Small Hackathon 2026" (June 5–15, 2026)
- **Submission bar:** a judge uploads 1 photo, types a name + 3-sentence memory,
  clicks Generate, and within 3 minutes sees 5 illustrated scenes, hears the
  narration, and downloads a PDF that closes on the final page.

---

## 1. Product in one picture

```
   Caregiver                         HF Space (CPU, no GPU, no torch)                         Modal (GPU)
   ─────────                         ─────────────────────────────────                       ───────────
   uploads photos  ─────────────▶    Gradio app (app/main.py)                                 vision        A10G   MiniCPM-V 4.6
   + writes memory                   ├─ Tab 1  Create a story                 ──HTTPS──▶       story         A10G   MiniCPM4.1-8B
                                     ├─ Tab 2  Your storybook                 ──HTTPS──▶       illustration  A100   FLUX.1-schnell ×5 ∥
                                     └─ Tab 3  How did it go?                 ──HTTPS──▶       tts           A10G   VoxCPM2
                                     orchestrator → pipeline steps            ──HTTPS──▶       adaptation    T4     MiniCPM5-1B
                                     pdf/ (WeasyPrint, CPU)
                                          │ huggingface_hub
                                          ▼
                                     Private HF Dataset  (reactions.jsonl, stories.jsonl)
```

Two deployment targets that **never share a process**: the CPU Space (UI +
orchestration + PDF) and the Modal GPU services (inference). They talk only over
authenticated HTTPS.

---

## 2. Non-negotiable product decisions

These are deliberate and locked. Do not refactor them away (see `docs/DECISIONS.md`).

| # | Decision | Where enforced |
|---|---|---|
| 1 | **The final page is always** `"{person_name} looked out at everything she had made, and it was good."` over the person's first photo, full page, no other text. | `app/pdf/builder.py`, `app/pdf/templates/storybook.html`, narration tail |
| 2 | **The narration voice is always** *"A warm, unhurried voice like a kind grandmother reading a bedtime story, speaking slowly and clearly, with gentle pauses between sentences."* Not configurable. | `app/pipeline/narrator.py`, TTS endpoint default |
| 3 | **Audience is the caregiver**, not "everyone." All copy is warm; never clinical. **Never say "dementia" / "model" / "inference" in the UI.** | all UI copy, error strings |
| 4 | **The Space has zero GPU code.** No `torch` import under `app/`. Ever. | `app/**` |
| 5 | **Illustrations generate in parallel** (`ThreadPoolExecutor`, 5 workers), never sequentially. | `app/pipeline/illustrator.py` |
| 6 | **The adaptive feedback loop is a core feature**, not a nice-to-have — it earns the "Best Agent" angle. | feedback tab → storage → adapter → story |
| 7 | Pronoun is **"she"** universally for the demo (acknowledged trade-off, ADR-003). | final page text |

---

## 3. The five models (measured params ≈29.8B total / 32B limit)

| Role | Model (HF repo) | Params (actual) | VRAM | Modal GPU | OpenBMB? |
|---|---|---|---|---|---|
| Vision | `openbmb/MiniCPM-V-4.6` | 1.300B | ~4GB | A10G | ✅ |
| Story | `openbmb/MiniCPM4.1-8B` | 8.185B | ~16GB | A10G | ✅ |
| Illustration | `black-forest-labs/FLUX.1-schnell` + watercolour LoRA | 16.95B pipeline (11.9B transformer + 4.76B T5 + CLIP/VAE + 0.09B LoRA) | ~24GB | A100-40GB *(min_containers=1)* | ❌ (only non-OpenBMB) |
| TTS | `openbmb/VoxCPM2` | 2.290B | ~8GB | A10G | ✅ |
| Adaptation | `openbmb/MiniCPM5-1B` *(fallback `MiniCPM3-4B`)* | 1.081B | ~3GB | T4 | ✅ |

**Totals:** four OpenBMB models = **12.86B**; full system (every loaded weight) =
**≈29.8B** — under the 32B limit, ~2.2B headroom (quantize FLUX if more is needed).
See `docs/MODELS.md` for the measured breakdown.

**Watercolour LoRA:** prefer a high-liked `watercolor storybook lora flux`;
fallback `alvdansen/softpastel`. Weight **0.7–0.8**. Applied once in `@modal.enter`.
**Illustration output:** 512×768 portrait PNG, 4 inference steps.
Substitution policy: see `docs/MODELS.md` (never drop an OpenBMB model for a
non-OpenBMB one without explicit review).

---

## 4. The pipeline & data contracts

### 4.1 Shared types (defined in `app/pipeline/orchestrator.py`)

```python
class SceneDict(TypedDict):
    scene_number: int          # 1–5
    text: str                  # 2–4 sentences, 2nd person, present tense
    illustration_prompt: str   # enriched FLUX prompt
    emotional_beat: str        # e.g. "quiet pride"

@dataclass
class PhotoAnalysis:           # (lives in app/pipeline/photo_analyzer.py)
    era: str
    people_descriptions: list[str]
    locations: list[str]
    emotional_register: str
    key_objects: list[str]
    style_period: str

@dataclass
class StoryResult:
    scenes: list[SceneDict]
    images: list[Image.Image]
    audio_path: Path
    pdf_path: Path
    session_id: str
    person_name: str
    adaptation_weights: dict[str, float] = field(default_factory=dict)
```

### 4.2 Stages, contracts, and progress checkpoints

| # | Stage / module | In → Out | Progress | Modal call |
|---|---|---|---|---|
| 1 | **Vision** `photo_analyzer.py` | `(photos: list[Path], person_name)` → `PhotoAnalysis` | 0→15% | `MiniCPMVision.analyze(images_b64, person_name)` |
| 2 | **Story** `story_generator.py` | `(PhotoAnalysis, memory_text, person_name, event, adaptation_weights?)` → `list[SceneDict]` (exactly 5) | 15→35% | `StoryGenerator.generate(...)` |
| 3 | **Illustration** `illustrator.py` | `(scenes, style_period)` → `list[Image]` (5, in order) — **parallel** | 35→75% | `Illustrator.illustrate(prompt, scene_number, style_period)` ×5 |
| 4 | **Narration** `narrator.py` | `(scenes, voice_description)` → `Path` (WAV) | 75→90% | `Narrator.narrate(text, voice_description)` |
| 5 | **PDF** `pdf/builder.py` | `(scenes, images, person_name, event, first_photo, output_path)` → `Path` — **CPU, no Modal** | 90→100% | — |
| 6 | **Persist** `session_store.save_story_metadata` | metadata → HF Dataset | — | — |

Loading-state copy (UI): 15% *"Looking at the photos…"* · 35% *"Writing the
story…"* · 75% *"Painting the illustrations…"* · 90% *"Recording the
narration…"* · 100% *"Your storybook is ready."*

### 4.3 Validation rules

- **Story:** exactly 5 scenes; each has all 4 keys; `len(text) > 20`. On bad JSON,
  retry once then raise `PipelineError`.
- **Illustration partial failure:** replace the failed image with a warm-cream
  (`#FDF6EC`) 512×768 placeholder, log a warning — never fail the whole run.
- **Narration:** concatenate scene texts with ` [pause] `, then append
  ` [pause] {final page text}` so the audio ends on the same line as the PDF.

---

## 5. The adaptive feedback loop (the "agent")

```
caregiver taps reaction per scene  (smiled | unsettled | asleep)
        ▼  feedback_tab → session_store.save_reaction()  → HF Dataset
next generation begins
        ▼  orchestrator calls session_store.load_reaction_history(session_id, days=7)
        ▼  if history: adapter.compute_adaptation_weights()  → Modal MiniCPM5-1B
        ▼  weights dict {professional_identity, family_relationships, place_and_home,
                         adventure_travel, nature_outdoors}  (each 0.0–1.0)
        ▼  passed into story_generator as SOFT constraints
story emphasises themes she responds to; de-emphasises themes that unsettle her
```

Scoring intuition: `smiled` ↑ the theme, `unsettled` ↓, `asleep` slightly ↓.
Weights are *soft* preferences in the prompt, never hard filters.

---

## 6. User interface (3 tabs)

`gr.Blocks(theme=gr.themes.Soft(), title="Memory Lantern", css="app/static/custom.css")`

**Session state** (`gr.State`, keyed by a UUID4 `session_id` minted on load):
`session_id, person_name, event, memory_text, uploaded_photos, photo_analysis,
scenes, images, audio_path, pdf_path, reaction_log, adaptation_weights,
generation_count`.

| Tab | id | Key components |
|---|---|---|
| **Create a story** | `tab_setup` | `gr.File`(multiple, images, 1–10) · name · event · memory (6 lines) · "Tips" accordion · **Generate** (primary, lg) · progress · status |
| **Your storybook** | `tab_story` | empty-state msg · title · story `gr.HTML` (warm cards) · `gr.Gallery`(cols=2) · `gr.Audio` · **Download PDF** · **Generate a new version** |
| **How did it go?** | `tab_feedback` | per-scene rows with 3 reaction buttons (smiled / unsettled / asleep) · notes box · **Save feedback** · 7-day `gr.Dataframe` history |

**Input validation** (before generation): photos present; name present; event
present; `memory_text ≥ 30 chars`. Returns a warm message string or `None`.

**UX copy rules:** verbs not nouns on buttons; warm error messages
("Something went wrong — please try again in a moment"); address the family
member, never "the patient"; framing is "preserve / celebrate / share."

---

## 7. Storage (private HF Dataset + temp files)

Repo from `HF_DATASET_REPO`, **always private** (contains family data).

```
memory-lantern-data/
├── reactions/reactions.jsonl    # append-only
└── stories/stories.jsonl        # append-only
```

**reactions.jsonl record:** `{session_id, date, scene_number, reaction, notes, timestamp}`
(`reaction ∈ {smiled, unsettled, asleep}`).
**stories.jsonl record:** `{session_id, date, person_name, event, scene_count,
emotional_beats[], adaptation_weights_used{}, generation_number, timestamp}`.

**`session_store.py`:** `save_reaction(session_id, scene_number, reaction, notes="")`,
`load_reaction_history(session_id, days=7) -> list[dict]`,
`save_story_metadata(session_id, story, adaptation_weights)`.
Write pattern: download JSONL → append line → re-upload via `huggingface_hub`
(race condition acceptable for a single-family demo, ADR-006).

**`asset_store.py`:** generated images/audio/PDF live in `/tmp/{session_id}/…`
for the session: `save_images`, `save_audio`, `save_pdf`, `cleanup_session`.

**Privacy (absolute):** photos are **never** persisted to HF/Modal beyond the
inference call; reaction log and story metadata contain **no photos**; dataset is
private; session IDs are UUIDs with no PII.

---

## 8. PDF (WeasyPrint + Jinja2, CPU only — 7 pages)

A5, warm cream `#FDF6EC`, **Lora** Google Font, dark-brown `#3D2B1F` text, tan
`#C4956A` accent. Images embedded as base64 data URIs (PNG for illustrations,
JPEG for photos).

| Page | Content |
|---|---|
| Cover | `person_name` (Lora Bold 28–36px) + `event` (italic) inside an 8px tan border |
| Scene 1–5 | illustration top 60% (`object-fit: cover`) + scene text bottom 40% (18px, line-height 1.8) |
| **Final** | first uploaded photo full-bleed + the hardcoded line, italic, centred at bottom, light text with shadow — **always rendered, never conditional** |

`build_pdf(scenes, images, person_name, event, first_photo, output_path) -> Path`.
Requires `packages.txt` (libpango, libcairo2, libgdk-pixbuf2.0-0, libffi-dev,
shared-mime-info) on the Space, and internet access for the Lora font.

---

## 9. Prompts (exact templates in `docs/PROMPTS.md` — do not improvise)

- **Vision:** system = "return ONLY valid JSON"; user asks for the 6
  `PhotoAnalysis` fields about `{person_name}`'s photos.
- **Story:** 2nd person, present tense, 2–4 sentences/scene; never say "remember"
  / illness; person's name ≥1× per scene; gentle arc ordinary→meaningful→tender
  peak→reflection→looking-back; returns a JSON array of 5 scenes. Adaptation
  weights injected as "emphasise these / reduce these" when present.
- **Illustration:** `build_illustration_prompt(scene, style_period, era)` appends
  an `ERA_STYLE_MAP[era]` modifier + fixed suffix *"soft watercolour
  illustration, warm gentle tones, storybook style, hand-painted feel, no text,
  no words."*
- **Adaptation:** scores 5 named themes 0.0–1.0 from the reaction log; returns
  ONLY the JSON object.
- **Final page text:** hardcoded constant, **not** a prompt.

---

## 10. Errors (warm, never crash Gradio — `docs/ERRORS.md`)

Hierarchy in `app/utils/errors.py`:
`MemoryLanternError` ⊃ `PipelineError(user_message, stage, original)`,
`ValidationError`, `StorageError`, `ModalEndpointError(PipelineError)`.

The orchestrator catches everything, logs the full trace to stderr, and returns
a **user-facing string** (or `StoryResult`). Examples: vision down → *"Something
went wrong while looking at the photos. Please try again."*; TTS fails →
*"The narration couldn't be recorded this time. Your storybook will still be
available as text and PDF."*; HF write fails → silent + log (UI still shows
success). Startup checks the 4 env vars and warns (banner) if missing.

---

## 11. Configuration & deployment

**Env vars (HF Space secrets / `.env`):** `MODAL_TOKEN_ID`,
`MODAL_TOKEN_SECRET`, `HF_TOKEN`, `HF_DATASET_REPO`.

**Modal:** `modal setup`; create secret `huggingface-token`; deploy each
endpoint (`modal deploy modal_backends/<x>_endpoint.py`); HF Space calls them via
`modal.Cls.from_name("memory-lantern-<x>", "<Class>").<method>.remote(...)`.
Illustration keeps **1 warm container**; others tolerate cold starts.

**HF Space:** Gradio SDK, **CPU Basic**, Python 3.11, `app/main.py` entrypoint,
4 secrets, `packages.txt` for WeasyPrint. Push to `main` auto-deploys via
`.github/workflows/deploy.yml` (app only — Modal deploys stay manual).

---

## 12. Scope (`docs/SCOPE.md`)

**In scope:** full 5-stage pipeline; story HTML; gallery; audio; PDF + final
page; adaptive loop; warm UI + CSS; graceful errors; progress.
**Explicitly out:** auth/login, multi-language narration, voice cloning, multiple
storybooks, sharing, mobile app, style selector, **custom final-page text**,
per-scene regeneration, memory editing, multiple people per book.
**Cut order if behind:** regenerate button → rich HTML → CI/CD → extra tests.

---

## 13. Prize mapping (`docs/PRIZES.md`)

| Prize | How we win it |
|---|---|
| OpenBMB $10k | 4 load-bearing OpenBMB models — name each in README + demo |
| Backyard AI track | a specific real user (a caregiver) + a real, under-served problem |
| Community Choice | the unchanging final page — shareable emotional peak |
| Best Agent | observe→store→reason→act→repeat loop with persistent memory |
| Tiny Titan (at risk) | 12.86B across the 4 OpenBMB models (~29.8B incl. FLUX), 1B model on a T4, CPU-only Space |

---

## Source-of-truth map

| Topic | Authoritative doc |
|---|---|
| Master context & rules | `docs/CLAUDE.md` |
| System architecture & boundaries | `docs/architecture.md`, `docs/ARCHITECTURE copy.md` |
| Modal endpoints | `docs/MODAL.md` |
| Pipeline & data contracts | `docs/PIPELINE.md` |
| UI components & copy | `docs/USER_INTERFACE.md` |
| Storage schema | `docs/STORAGE.md` |
| PDF structure | `docs/PDF.md` |
| Prompts | `docs/PROMPTS.md` |
| Models | `docs/MODELS.md` |
| Errors | `docs/ERRORS.md` |
| Deployment | `docs/DEPLOYMENT.md`, `docs/hf_spaces_deployment.md`, `docs/modal_deployment.md` |
| Decisions (ADRs) | `docs/DECISIONS.md` |
| Scope | `docs/SCOPE.md` |
| Prizes | `docs/PRIZES.md` |

> The build sequence for turning this spec into working code lives in
> **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)**.
