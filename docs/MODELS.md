# MODELS.md — Model Specifications

Do not substitute any model without updating this file and ARCHITECTURE.md.
Every model here was chosen deliberately — see "Why chosen" before replacing.

---

## Parameter budget

Counts below are **measured** from each model's safetensors metadata on Hugging
Face (June 2026), not estimates.

| Role | Component | Parameters (actual) | VRAM (bf16) |
|---|---|---|---|
| Vision | MiniCPM-V 4.6 | 1.300B | ~4GB |
| Story | MiniCPM4.1-8B | 8.185B | ~16GB |
| TTS | VoxCPM2 | 2.290B | ~8GB |
| Adaptation | MiniCPM5-1B | 1.081B | ~3GB |
| **OpenBMB subtotal (4 models)** | | **12.856B** | — |
| Illustration | FLUX.1-schnell — transformer (MMDiT) | 11.891B | ~24GB |
| Illustration | FLUX — T5-XXL text encoder | 4.762B | (incl. above) |
| Illustration | FLUX — CLIP-L text encoder | 0.123B | |
| Illustration | FLUX — VAE | 0.084B | |
| Illustration | watercolour LoRA (`Flux_Aquarell_Watercolor_v2`) | 0.086B | |
| **FLUX pipeline subtotal** | | **16.946B** | — |

### Totals vs the 32B hard limit

- **Full system — every weight loaded** (incl. FLUX's text encoders + VAE + LoRA):
  **≈ 29.80B** → under 32B, but headroom is only **~2.2B**.
- **Generative-core view** (FLUX counted as its 11.9B transformer only):
  **≈ 24.83B**.

The previously documented "24.3B" undercounted FLUX by omitting its **4.76B
T5-XXL** text encoder (plus CLIP + VAE). If judges count every loaded weight, the
honest figure is **~29.8B**. The four OpenBMB models alone are **12.86B**.

If we need more headroom, quantize the FLUX text encoder / transformer (e.g.
8-bit or FP8) — this does not touch the OpenBMB prize models. Do not add any
model that pushes the full-system total over ~31B without explicit approval.

---

## Vision Model

**Model:** `openbmb/MiniCPM-V-4.6`
**Parameters:** 1.3B (SigLIP2-400M vision encoder + Qwen3.5-0.8B LLM)
**VRAM:** ~4GB bf16, ~2-3GB at 4-bit quantisation
**Modal GPU:** A10G (24GB VRAM — comfortable)
**Inference latency:** ~2-4 seconds for a batch of up to 10 photos
**ZeroGPU compatible:** Yes

**Why chosen:**
- OpenBMB model — counts toward $10k prize
- Outperforms 7B-8B vision models on OCRBench, DocVQA at 19x lower token cost
- Mixed 4x/16x visual token compression — efficient multi-image batching
- Runs on edge hardware — proves "small model" thesis
- Supports multi-image input in a single forward pass (all uploaded photos at once)

**What it extracts from photos:**
- Approximate era/decade (clothing, film grain, colour saturation)
- People descriptions (age, relationship cues, proximity)
- Locations (indoor/outdoor, type of place)
- Emotional register of each photo
- Key objects (cars, uniforms, tools — anchors for story details)
- Style period (used to inform illustration era)

**Loading code pattern:**
```python
from transformers import AutoTokenizer, AutoModel
import torch

model = AutoModel.from_pretrained(
    "openbmb/MiniCPM-V-4.6",
    trust_remote_code=True,
    torch_dtype=torch.bfloat16,
    device_map="cuda"
)
tokenizer = AutoTokenizer.from_pretrained(
    "openbmb/MiniCPM-V-4.6",
    trust_remote_code=True
)
```

---

## Story Generation Model

**Model:** `openbmb/MiniCPM4.1-8B`
**Parameters:** 8B
**VRAM:** ~16GB bf16, ~9GB at 4-bit quantisation
**Modal GPU:** A10G (24GB VRAM — fine at bf16)
**Inference latency:** ~15-30 seconds for a 5-scene story (~800 tokens output)
**ZeroGPU compatible:** Yes

**Why chosen:**
- OpenBMB model — counts toward $10k prize
- Reasoning-capable variant — holds multiple constraints simultaneously
  (names, relationships, emotional register, narrative arc, factual fidelity)
- Better than fluent-but-shallow smaller models for grounded persona narrative
- Qwen3-8B would be comparable quality but loses the OpenBMB prize angle

**What it generates:**
- 5 SceneDict objects, each with:
  - `scene_number` (1-5)
  - `text` (2-4 sentences, second-person present tense, warm tone)
  - `illustration_prompt` (enriched FLUX prompt, era-specific)
  - `emotional_beat` (e.g. "triumph", "tenderness", "quiet pride")

**Critical prompt constraints — see PROMPTS.md for exact templates:**
- Always second-person ("You are standing in...")
- Always present tense
- Never mention dementia, memory loss, illness, or hospitals (unless that IS the memory)
- Scene 5 must set up the final page ("you look out at everything...")
- Names of people mentioned in the memory must appear in the story

---

## Illustration Model

**Model:** `black-forest-labs/FLUX.1-schnell`
**Parameters:** 12B (DiT: ~12B + text encoders: ~4.5B — total pipeline ~16.5B loaded)
**VRAM:** ~24GB without CPU offloading (preferred for speed), ~12GB with offloading
**Modal GPU:** A100 40GB (required — A10G at 24GB is marginal without offloading)
**Inference latency:** ~8-15 seconds per image at 512×512, 4 inference steps
**ZeroGPU compatible:** Yes (H200 has 70GB)

**Why chosen:**
- Best open-source text-to-image quality at this parameter range
- 4-step inference (schnell = fast) — 5 illustrations in ~12-15s parallel
- Supports LoRA for style control
- Apache 2.0 license (commercial use permitted)
- NOT an OpenBMB model — the only non-OpenBMB model in the stack

**LoRA:**
- Target: watercolour/soft illustrated style
- Recommended: search HF for `watercolor storybook lora flux` — pick highest-liked
- Fallback: `alvdansen/softpastel` or `artifex_forge/flux-watercolor`
- LoRA weight: 0.7-0.8 (too high = cartoonish, too low = photorealistic)
- Apply in `@modal.enter` so it loads once, not per request

**Image output spec:**
- Resolution: 512×768 (portrait — storybook page proportions)
- Format: PNG bytes
- Style modifier always appended to prompt:
  `"soft watercolour illustration, warm gentle tones, storybook style, [era]"`

**Parallelism:**
- The orchestrator calls this endpoint 5 times concurrently via ThreadPoolExecutor
- Modal handles the concurrency — each call gets its own GPU allocation
- Do NOT run 5 images sequentially — latency goes from ~12s to ~60s

---

## TTS Model

**Model:** `openbmb/VoxCPM2`
**Parameters:** 2B
**VRAM:** ~8GB bf16
**Modal GPU:** A10G
**Inference latency:** RTF ~0.3 on A10G (3 seconds to generate 10 seconds of audio)
**ZeroGPU compatible:** Yes

**Why chosen:**
- OpenBMB model — counts toward $10k prize
- Tokenizer-free diffusion autoregressive architecture — preserves acoustic detail
- Supports natural-language voice design: specify voice in prose, not parameters
- 30 languages — supports multilingual families
- 48kHz output — high quality audio for the narration demo
- Apache 2.0 license

**Voice specification (hardcoded — do not make configurable):**
```
"A warm, unhurried voice like a kind grandmother reading a bedtime story,
speaking slowly and clearly, with gentle pauses between sentences."
```

**Output spec:**
- Format: WAV bytes
- Sample rate: 48kHz
- The orchestrator saves to a temp file and returns the path to Gradio

**Loading pattern:**
```python
from voxcpm import VoxCPM
model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
```

---

## Adaptation Model

**Model:** `openbmb/MiniCPM5-1B`
**Fallback if unavailable:** `openbmb/MiniCPM3-4B` (same role, 4B params)
**Parameters:** 1B (fallback: 4B)
**VRAM:** ~3GB bf16 (fallback: ~8GB)
**Modal GPU:** T4 (cheapest Modal GPU — this model is tiny)
**Inference latency:** <2 seconds
**ZeroGPU compatible:** Yes

**Why chosen:**
- OpenBMB model — counts toward $10k prize
- Task is simple JSON reasoning, not creative writing — 1B is sufficient
- Cheapest possible GPU tier (T4) — demonstrates small-model efficiency thesis
- Running a 1B model on a T4 for the agent loop is a good story for judges

**What it does:**
- Input: last 7 days of reaction logs (JSON array)
- Output: adaptation_weights dict
- Example output:
  ```json
  {
    "professional_identity": 0.85,
    "family_relationships": 0.70,
    "place_and_home": 0.60,
    "adventure_travel": 0.30,
    "nature_outdoors": 0.45
  }
  ```
- These weights are passed as soft constraints to the story generator
- See PROMPTS.md for the exact adaptation prompt template

---

## Model substitution policy

If a model becomes unavailable or broken, use this priority order:

| Original | First fallback | Second fallback |
|---|---|---|
| MiniCPM-V 4.6 | MiniCPM-o 4.5 (9B, loses Tiny Titan) | Qwen2-VL-7B (loses OpenBMB prize) |
| MiniCPM4.1-8B | MiniCPM3-4B | Qwen3-8B (loses OpenBMB prize) |
| FLUX.1-schnell | SDXL-Turbo (lower quality) | None — image gen is required |
| VoxCPM2 | VoxCPM1.5 | Kokoro-82M (loses OpenBMB prize) |
| MiniCPM5-1B | MiniCPM3-4B | Skip adaptation (degraded feature) |
