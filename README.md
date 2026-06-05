# Memory Lantern 🏮

> Turn a family memory and a few photos into a personalised illustrated storybook, narrated in a warm voice — built for families caring for loved ones with dementia.

![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
![Gradio](https://img.shields.io/badge/UI-Gradio-orange.svg)
![Modal](https://img.shields.io/badge/inference-Modal-green.svg)
![HF Spaces](https://img.shields.io/badge/deploy-HF%20Spaces-yellow.svg)

<!-- DEMO GIF PLACEHOLDER -->

## What it does

Memory Lantern takes a written memory and a handful of photos and turns them into a
five-scene illustrated storybook, narrated aloud in a warm, unhurried voice. It is
designed for elderly users with early-stage dementia and the caregivers who support
them. Caregivers can log how their loved one reacted to each scene, and the system
gently adapts future stories toward the themes that bring comfort and recognition.

## Architecture

- **Frontend / orchestration:** A Gradio app hosted on Hugging Face Spaces (CPU tier).
- **Inference backend:** Each model runs as a separate [Modal](https://modal.com)
  deployment with a persistent GPU. The Gradio app calls these endpoints over HTTPS.
- **Persistent state:** A private Hugging Face Dataset acts as a key-value store for
  reaction logs and generated story metadata.
- **PDF generation:** WeasyPrint runs on the HF Space CPU.

| Role | Model | Modal GPU |
|---|---|---|
| Vision / photo analysis | MiniCPM-V 4.6 | A10G |
| Story generation | MiniCPM4.1-8B | A10G |
| Illustration | FLUX.1-schnell + watercolour LoRA | A100-40GB |
| TTS narration | VoxCPM2 | A10G |
| Adaptation agent | MiniCPM5-1B | T4 |

See [`docs/architecture.md`](docs/architecture.md) for the full system diagram.

## Setup

```bash
# 1. Clone
git clone https://huggingface.co/spaces/your-username/memory-lantern
cd memory-lantern

# 2. Install the Gradio app dependencies (no torch — inference is remote)
pip install -r requirements.txt
pip install -r requirements-dev.txt   # for running tests locally

# 3. Configure environment
cp .env.example .env
# Edit .env with your Modal tokens, HF token, and dataset repo

# 4. Deploy the Modal inference backends (one-time, manual)
pip install -r requirements-modal.txt
modal setup
modal deploy modal_backends/vision_endpoint.py
modal deploy modal_backends/story_endpoint.py
modal deploy modal_backends/illustration_endpoint.py
modal deploy modal_backends/tts_endpoint.py
modal deploy modal_backends/adaptation_endpoint.py

# 5. Run the app locally
python app/main.py
# Open http://localhost:7860
```

For full deployment instructions:

- [`docs/modal_deployment.md`](docs/modal_deployment.md) — deploying the GPU backends
- [`docs/hf_spaces_deployment.md`](docs/hf_spaces_deployment.md) — configuring the HF Space

## Testing

```bash
python -m pytest tests/ -v --tb=short
```

## Project status

This repository is a fully navigable scaffold. The UI shell, orchestration plumbing,
PDF assembly, and Modal endpoint definitions are in place. Model inference bodies are
stubbed with `NotImplementedError` and documented endpoint contracts, ready to be
filled in.
