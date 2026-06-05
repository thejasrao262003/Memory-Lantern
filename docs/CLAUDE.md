# CLAUDE.md — Master Context for Memory Lantern

This file is the single source of truth for Claude Code working on this project.
Read this file first. Read ALL referenced files before writing any code.
Do not deviate from the decisions documented here without explicit instruction.

---

## What this project is

Memory Lantern transforms personal photos and a short written memory into a
personalised illustrated storybook, narrated in a warm voice. It is built
specifically for families caring for loved ones with early-stage dementia.

This is a Gradio application hosted on Hugging Face Spaces. All heavy model
inference runs on Modal GPU endpoints. The HF Space is CPU-only.

This project was designed to compete in the Gradio + Hugging Face
"Build Small Hackathon 2026" (June 5–15, 2026).

---

## Non-negotiable product decisions

These decisions were made deliberately. Do not refactor them away.

1. The last page of every generated storybook ALWAYS reads:
   `"{person_name} looked out at everything she had made, and it was good."`
   followed by the person's photo, full page, no other text.
   This is the emotional centrepiece of the demo. It is hardcoded in `app/pdf/builder.py`.

2. The TTS voice is ALWAYS described as:
   `"A warm, unhurried voice like a kind grandmother reading a bedtime story,
   speaking slowly and clearly."`
   Do not make this configurable. It must feel the same every time.

3. The audience is NOT "everyone." The primary user is a family member or
   professional caregiver of an elderly person with early-stage dementia.
   All UX copy, error messages, and tone must reflect this.

4. The Gradio app contains zero GPU code. No torch imports in app/. Ever.
   All inference is behind Modal endpoints.

5. Illustrations are generated in parallel (ThreadPoolExecutor), never sequentially.
   Sequential generation of 5 FLUX images is unacceptably slow for the demo.

6. The adaptive feedback loop (caregiver reaction → tomorrow's story) is a
   core feature, not a nice-to-have. It is what earns the "Best Agent" badge.
   Do not reduce it to a static pipeline.

---

## File map — read before touching any module

| File | Purpose |
|---|---|
| CLAUDE.md | This file. Master context. Read first. |
| ARCHITECTURE.md | Full system diagram, data flow, component boundaries |
| MODAL.md | Every Modal endpoint: GPU specs, model, method signatures, deploy commands |
| USER_INTERFACE.md | Every Gradio component, tab layout, state machine, UX copy |
| PIPELINE.md | The five-stage inference pipeline, data contracts between stages |
| STORAGE.md | HF Datasets schema, session management, reaction log format |
| PDF.md | Storybook PDF structure, Jinja2 template spec, the final page rule |
| PROMPTS.md | Exact prompt templates for every model. Do not improvise prompts. |
| PRIZES.md | Hackathon prize categories and how each architectural decision maps to them |
| DEPLOYMENT.md | Step-by-step: Modal deploy, HF Space config, secrets, CI/CD |
| MODELS.md | Every model: exact HF repo, parameter count, VRAM, why it was chosen |
| ERRORS.md | Error taxonomy, user-facing messages, fallback behaviour |
| TESTING.md | Test strategy, fixture data, what must be mocked |

---

## Critical constraints — check before every code change

- Total model parameters across the system: ≈29.8B measured, under the 32B limit
  (four OpenBMB models = 12.86B; FLUX full pipeline ≈ 16.9B incl. T5/CLIP/VAE +
  LoRA). Headroom ~2.2B — quantize FLUX if we need more. See MODELS.md.
- HF Space tier: CPU Basic (no GPU, no torch)
- Modal inference: each model is a separate Modal App, not a monolith
- All models are open-source (no OpenAI, Anthropic, or closed APIs)
- OpenBMB models used: MiniCPM-V 4.6, MiniCPM4.1-8B, VoxCPM2, MiniCPM5-1B
  (these four models qualify for the OpenBMB $10k prize category)
- FLUX.1-schnell is the ONLY non-OpenBMB model in the inference stack

---

## When in doubt

Ask: "Does this change make the demo more emotionally powerful, or less?"
If less, don't make it.

Ask: "Does this change require GPU on the HF Space?"
If yes, don't make it.

Ask: "Does this change break the adaptive feedback loop?"
If yes, don't make it.
