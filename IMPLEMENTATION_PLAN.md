# Memory Lantern — Implementation Plan

A step-by-step build plan to take the current **scaffold** to a **demo-ready**
submission for the Build Small Hackathon (June 5–15, 2026).

Read alongside **[SPEC.md](SPEC.md)** (the *what*) — this is the *how* and the
*in what order*. The detailed contracts live in `docs/`.

---

## Legend

| Mark | Meaning |
|---|---|
| ✅ | Done — exists in the scaffold and matches spec |
| 🟡 | Partial — exists but must be reconciled to the spec (see task) |
| ⬜ | Not started |
| 🔒 | Non-negotiable (see `docs/DECISIONS.md`) — implement exactly |
| ⚡ | On the critical path to "demo ready" |

**Current state:** the full directory tree, importable stubs, a working Gradio
3-tab shell, a working prompt builder, a working (A4) PDF builder, and 5 Modal
endpoint stubs all exist and pass `pytest` (13 passed, 1 skipped). Everything
below is either reconciliation (🟡) or net-new (⬜).

---

## The critical path (what must work for the demo)

```
   ⚡ Phase 1  Modal endpoints deploy & return real data
        │      (vision → story → illustration → tts ; adaptation can lag)
        ▼
   ⚡ Phase 2  Orchestrator calls them end-to-end with real contracts
        │
        ▼
   ⚡ Phase 3  PDF assembles with the 🔒 final page
        │
        ▼
   ⚡ Phase 5  Gradio "Generate" button wired → story renders, audio plays, PDF downloads
        │
        ▼
   ⚡ Phase 7  Deployed to a public HF Space + 5 Modal apps live

   Phase 4 (storage + adaptive loop) and Phase 6 (error polish) run in parallel
   and are "ship if time allows" — except the final-page rule, which is 🔒.
```

> **Definition of demo-ready** (`docs/SCOPE.md`): open the Space → upload 1 photo,
> type "Margaret" + a 3-sentence memory → Generate → within 3 min see 5
> illustrated scenes, hear narration, download a PDF ending on
> *"Margaret looked out at everything she had made, and it was good."*

---

## Phase 0 — Foundations & reconciliation

Bring the scaffold's shared pieces in line with the spec **before** building on
them, so contracts don't churn later.

- [ ] 🟡 **`app/utils/errors.py`** — add the exception hierarchy from
  `docs/ERRORS.md`: `MemoryLanternError` → `PipelineError(user_message, stage,
  original)`, `ValidationError`, `StorageError`, `ModalEndpointError(PipelineError)`.
  Move the ad-hoc `ModalEndpointError` out of `orchestrator.py` and import it from here.
- [ ] 🟡 **`StoryResult`** (`orchestrator.py`) — add `session_id: str`,
  `person_name: str`, `adaptation_weights: dict[str, float]` to match `docs/PIPELINE.md`.
- [ ] 🟡 **Progress checkpoints** — change orchestrator from `10/30/60/90/100`
  to the spec's **`15/35/75/90/100`** with the exact loading-state copy.
- [ ] ⬜ **`packages.txt`** (project root) — `libpango-1.0-0`, `libcairo2`,
  `libgdk-pixbuf2.0-0`, `libffi-dev`, `shared-mime-info` (WeasyPrint on the Space).
- [ ] ⬜ **`app/static/custom.css`** — warm cream container, tan tab border,
  accent primary button, rounded gallery images (`docs/USER_INTERFACE.md`).
- [ ] ⬜ **`session_id`** — mint a `uuid4()` into `gr.State` on app load.
- [ ] ✅ Requirements files, `.env.example`, `.gitignore`, tests harness.

**Done when:** `pytest` still green; `app/utils/errors.py` importable; `StoryResult`
has all 7 fields; `packages.txt` and `custom.css` exist.

---

## Phase 1 — Modal inference backends ⚡

Each endpoint is independent; implement and verify **one at a time** with
`modal run` before wiring the Space. Reference: `docs/MODAL.md`, `docs/MODELS.md`,
`docs/PROMPTS.md`.

### 1.0 Shared config 🟡
- [ ] Reconcile `modal_backends/shared/modal_config.py` to `docs/MODAL.md`:
  per-endpoint images on a shared `BASE_IMAGE`, per-endpoint timeouts
  (vision 60s, story 120s, illustration 60s, tts 120s, adaptation 30s), the
  `huggingface-token` secret name, and `keep_warm=1` for illustration only.

### 1.1 Vision — `memory-lantern-vision` (A10G) ⚡
- [ ] `@modal.enter` loads `openbmb/MiniCPM-V-4.6` (bf16, trust_remote_code).
- [ ] `analyze(images_b64, person_name) -> dict` decodes images, prompts with
  `build_vision_prompt`, parses to the 6 `PhotoAnalysis` fields.
- [ ] Verify: `modal run … MiniCPMVision.analyze` returns valid JSON.

### 1.2 Story — `memory-lantern-story` (A10G) ⚡
- [ ] `@modal.enter` loads `openbmb/MiniCPM4.1-8B`.
- [ ] `generate(photo_analysis, memory_text, person_name, event, adaptation_weights=None) -> list[dict]`
  using the exact `STORY_SYSTEM_PROMPT` + `build_story_prompt`.
- [ ] Returns **exactly 5** scenes; passes the `docs/PROMPTS.md` acceptance
  checklist (2nd person, present tense, name ≥3 scenes, no clinical language).

### 1.3 Illustration — `memory-lantern-illustration` (A100-40GB, keep_warm=1) ⚡🔒
- [ ] `@modal.enter` loads FLUX.1-schnell **and applies the watercolour LoRA once**
  (weight 0.7–0.8).
- [ ] `illustrate(prompt, scene_number, style_period) -> bytes` → 512×768 PNG, 4 steps.
- [ ] Verify a single image renders in the watercolour style.

### 1.4 TTS — `memory-lantern-tts` (A10G) 🔒
- [ ] `@modal.enter` loads `openbmb/VoxCPM2` (`load_denoiser=False`).
- [ ] `narrate(text, voice_description=<🔒 hardcoded warm-voice string>) -> bytes`
  → 48kHz WAV.

### 1.5 Adaptation — `memory-lantern-adaptation` (T4)
- [ ] `@modal.enter` loads `openbmb/MiniCPM5-1B` (fallback `MiniCPM3-4B`).
- [ ] `adapt(reaction_log) -> dict[str,float]` over the 5 named themes via
  `build_adaptation_prompt`.

**Done when:** `modal app list` shows 5 deployed apps and each `modal run` smoke
test returns the spec-shaped payload.

---

## Phase 2 — Pipeline orchestration (on the Space) ⚡

No `torch` here — only Modal client calls. Reference: `docs/PIPELINE.md`,
`docs/MODAL.md` "Calling from HF Space".

- [ ] 🟡 **`photo_analyzer.analyze_photos`** — resize→base64 (`image_utils`),
  call `MiniCPMVision`, deserialise to `PhotoAnalysis`. Empty list → `ValidationError`;
  one bad photo → skip + warn.
- [ ] 🟡 **`story_generator.generate_story`** — build prompt, call `StoryGenerator`,
  parse + **validate 5 scenes**, enrich each `illustration_prompt` via
  `build_illustration_prompt`. Retry once on bad JSON.
- [ ] 🟡 **`illustrator.generate_illustrations`** ⚡🔒 — `ThreadPoolExecutor(max_workers=5)`,
  one `Illustrator().illustrate.remote` per scene, PNG→PIL, **preserve scene order**.
  Per-image failure → cream `#FDF6EC` 512×768 placeholder (never fail the run).
- [ ] 🟡 **`narrator.narrate_story`** — join scene texts with ` [pause] `, append
  ` [pause] {final page line}`, call `Narrator`, save WAV via `audio_utils`, return `Path`.
- [ ] 🟡 **`orchestrator.generate_storybook`** — run stages 1→5 with the
  `15/35/75/90/100` progress; before story, load reaction history and (if any)
  compute adaptation weights; assemble + return `StoryResult`; catch → return
  user-facing string (`docs/ERRORS.md`).

**Done when:** with the 5 endpoints live, calling `generate_storybook` from a
Python REPL on the Space produces 5 scenes + 5 images + a WAV + a PDF in < 3 min.

---

## Phase 3 — PDF assembly ⚡🔒

Reconcile the scaffold's working A4 builder to the `docs/PDF.md` spec.

- [ ] 🟡 **A5 + 7 pages**: cover (name + event in tan border) → 5 scene pages
  (illustration 60% / text 40%) → final page.
- [ ] 🔒 **Final page**: `first_photo` full-bleed + the hardcoded italic line,
  centred, light text + shadow. Always rendered; never conditional; not a parameter.
- [ ] 🟡 **Signature**: `build_pdf(scenes, images, person_name, event, first_photo, output_path)`.
- [ ] 🟡 **Template**: Lora font, palette (`#FDF6EC / #3D2B1F / #C4956A / #F5EBD8`),
  base64-embedded images (PNG illustrations, JPEG photo).
- [ ] ✅ Lazy WeasyPrint import (keeps module importable without native libs).

**Done when:** `test_pdf_builder.py` passes locally (with WeasyPrint installed),
the PDF is 7 pages, and the final page renders the 🔒 line over the photo.

---

## Phase 4 — Storage & the adaptive loop

Reference: `docs/STORAGE.md`, `docs/ARCHITECTURE copy.md` "Adaptation loop".

- [ ] 🟡 **`session_store`** — implement `save_reaction`, `load_reaction_history(days=7)`,
  `save_story_metadata(session_id, story, adaptation_weights)` using the
  download→append→upload JSONL pattern; **refuse to write to a public dataset**.
- [ ] 🟡 **`asset_store`** — `save_images/save_audio/save_pdf` to `/tmp/{session_id}/…`
  + `cleanup_session`.
- [ ] ⬜ **`adapter.compute_adaptation_weights`** — call the adaptation endpoint;
  return `{}` when there's no history (orchestrator then passes `None`).
- [ ] ⬜ **Loop wiring** — feedback tab saves reactions → next generation reads
  them → weights visibly change the story (must be demonstrable in the demo).

**Done when:** logging "smiled" on professional-identity scenes makes the next
generation lean into that theme, and the 7-day history table populates.

---

## Phase 5 — Gradio wiring ⚡

The scaffold lays out all components and leaves `# TODO: wire callback`.
Reference: `docs/USER_INTERFACE.md`.

- [ ] ⬜ **Validation** — `validate_inputs` (photos / name / event / `memory ≥ 30`),
  warm message strings.
- [ ] ⚡ **Generate callback** — `handle_generate` → `orchestrator.generate_storybook`
  with `gr.Progress`; on success populate state + Tab 2 and switch to `tab_story`;
  on error show a warm banner. Photos via `gr.File(file_count="multiple")`.
- [ ] ⬜ **Story rendering** — `render_story_html` warm cards; gallery; audio;
  `DownloadButton` wired to `pdf_path`.
- [ ] ⬜ **Regenerate** — re-run with same inputs (full regeneration, not per-scene).
- [ ] ⬜ **Feedback tab** — dynamic per-scene rows, reaction buttons →
  `save_reaction`, notes on scene 1, history dataframe refresh.
- [ ] ⬜ **Theme/CSS** — attach `app/static/custom.css`; startup env-var banner.

**Done when:** the whole flow is clickable in the browser with no dev knowledge,
and all copy obeys the UX rules (no "model/inference/dementia" in the UI).

---

## Phase 6 — Errors & resilience

Reference: `docs/ERRORS.md`.

- [ ] ⬜ Map every taxonomy row to its exact user-facing string.
- [ ] ⬜ Orchestrator returns strings (never throws into Gradio); full trace to stderr.
- [ ] ⬜ Partial-failure paths: illustration placeholder; TTS failure still ships
  text+PDF; HF write failure is silent + logged (UI shows success).
- [ ] ⬜ Startup `check_configuration()` lists missing env vars + UI banner.

**Done when:** killing any one endpoint mid-demo yields a calm message, never a stack trace in the UI.

---

## Phase 7 — Deployment ⚡

Reference: `docs/DEPLOYMENT.md`, `docs/hf_spaces_deployment.md`, `docs/modal_deployment.md`.

- [ ] ⬜ `modal setup` + create `huggingface-token` secret.
- [ ] ⚡ Deploy all 5 endpoints; `modal app list` shows "deployed".
- [ ] ⬜ Create the **private** HF Dataset with the two empty JSONL files.
- [ ] ⚡ Create the HF Space (Gradio, CPU Basic, py3.11), add the 4 secrets,
  ensure `packages.txt` is present.
- [ ] ⚡ Push → Space builds → three tabs load → logs show "Modal credentials detected."
- [ ] ⬜ Configure `.github/workflows/deploy.yml` (`HF_SPACE` var + `HF_TOKEN` secret).

**Done when:** a clean browser (no login) can run the full flow on the public Space URL.

---

## Phase 8 — Demo polish & submission

Reference: `docs/PRIZES.md` submission checklist.

- [ ] ⬜ README: storybook GIF/screenshot + OpenBMB models listed with HF links.
- [ ] ⬜ 2–3 min demo video: full flow; ≥20s of audio; the 🔒 final page; name all
  4 OpenBMB models; show the adaptive loop. Title avoids "dementia"
  ("Turn family memories into illustrated storybooks").
- [ ] ⬜ Verify < 3 min end-to-end generation.
- [ ] ⬜ Social post live (required for submission).

---

## Suggested 10-day schedule (June 5–15)

| Days | Focus | Phases |
|---|---|---|
| 5–6 | Foundations + deploy/verify vision & story endpoints | 0, 1.0–1.2 |
| 7 | Illustration (LoRA) + TTS endpoints | 1.3–1.4 |
| 8 | Orchestrator end-to-end + PDF final page | 2, 3 |
| 9 | Gradio wiring: generate → render → download | 5 (core) |
| 10 | Adaptation endpoint + storage + loop wiring | 1.5, 4 |
| 11 | Error polish + UX copy + CSS | 6, 5 (polish) |
| 12 | Deploy to public Space, end-to-end on prod | 7 |
| 13 | Buffer / fix cold-start & timing for the 3-min bar | — |
| 14 | Demo video + README + social post | 8 |
| 15 | **Submit.** No new features after day 13 (`docs/PRIZES.md`). | — |

**If behind, cut in this order** (`docs/SCOPE.md`): regenerate button → rich
HTML → CI/CD → extra tests. **Never cut:** the full pipeline, audio, the PDF
final page, three tabs, no-crash error handling.

---

## Guardrails — ask before every change (`docs/CLAUDE.md`)

1. *Does this make the demo more emotionally powerful, or less?* If less, don't.
2. *Does this require GPU on the HF Space?* If yes, don't.
3. *Does this break the adaptive feedback loop?* If yes, don't.
4. *Am I about to touch a 🔒 item* (final page, warm voice, OpenBMB models,
   parallel illustration, no-auth, JSONL storage)? Then re-read its ADR first.
