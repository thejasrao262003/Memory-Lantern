"""Shared Modal configuration: container images, GPUs, timeouts, and the
model-weight cache volume.

Targets the Modal 1.x API (``gpu="A10G"`` strings, ``min_containers``,
``scaledown_window``). Centralising this keeps the five endpoints consistent and
makes version bumps a one-file change.

**All model weights live in a single shared Modal Volume** mounted at
:data:`CACHE_DIR` with ``HF_HOME`` pointed inside it, so each model downloads
once and persists across cold starts instead of re-downloading per container.
"""

from __future__ import annotations

import modal

# ---------------------------------------------------------------------------
# Shared weight cache (one Volume for every endpoint)
# ---------------------------------------------------------------------------
CACHE_DIR = "/cache"
HF_HOME = f"{CACHE_DIR}/huggingface"

# create_if_missing → the volume is created on first deploy; all endpoints share
# it so a model pulled by one container is visible to the next.
weights_volume = modal.Volume.from_name("memory-lantern-hf-cache", create_if_missing=True)
VOLUMES = {CACHE_DIR: weights_volume}

# HF token for pulling models (gated or rate-limited). Create with:
#   modal secret create huggingface-token HF_TOKEN=hf_xxx
HF_SECRET = modal.Secret.from_name("huggingface-token")

# Environment baked into every image: send all HF caches into the volume and
# use the high-performance Xet transfer backend (hf_transfer is deprecated).
_CACHE_ENV = {
    "HF_HOME": HF_HOME,
    "HF_HUB_CACHE": f"{HF_HOME}/hub",
    "HF_XET_HIGH_PERFORMANCE": "1",
}

# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------
# Local Python source mounted into every endpoint container:
#   - "modal_backends": so each endpoint's own `from modal_backends.shared...`
#     import resolves at container runtime (the entrypoint file alone is not
#     enough — the package must be importable).
#   - "app": the prompt templates are the single source of truth in
#     app/utils/prompt_builder.py (docs rule: prompts live in app/, never in
#     modal_backends/). It pulls in no heavy deps (stdlib + typing only).
_LOCAL_SRC = ("app", "modal_backends")

# Most endpoints want the latest transformers (MiniCPM-V 4.6 needs 5.7's
# AutoModelForImageTextToText). MiniCPM4.1-8B is the exception: its
# trust_remote_code modeling file imports symbols removed in transformers 5.x
# (e.g. is_torch_fx_available), so the story image pins the 4.x line that the
# model card targets (`transformers>=4.56`). Each endpoint has its own image,
# so this divergence is isolated.
_DEFAULT_TRANSFORMERS = "transformers>=5.7.0"
_STORY_TRANSFORMERS = "transformers>=4.56,<5"

_COMMON_PKGS = ("torch>=2.3.0", "accelerate>=0.30.0", "Pillow>=10.0.0", "numpy>=1.26.0")


def _image(*extra_pkgs: str, transformers: str = _DEFAULT_TRANSFORMERS) -> modal.Image:
    """Build an endpoint image: pinned transformers + common deps + extras."""
    return (
        modal.Image.debian_slim(python_version="3.11")
        .pip_install(transformers, *_COMMON_PKGS, *extra_pkgs)
        .env(_CACHE_ENV)
        .add_local_python_source(*_LOCAL_SRC)
    )


VISION_IMAGE = _image("torchvision", "sentencepiece>=0.2.0")

STORY_IMAGE = _image("sentencepiece>=0.2.0", transformers=_STORY_TRANSFORMERS)

ILLUSTRATION_IMAGE = _image(
    "diffusers>=0.30.0",
    "safetensors>=0.4.0",
    "peft>=0.11.0",          # required for pipe.load_lora_weights
    "sentencepiece>=0.2.0",  # T5 text encoder tokenizer
    "protobuf>=4.25.0",
)

TTS_IMAGE = _image("voxcpm>=0.1.0", "soundfile>=0.12.0")

ADAPTATION_IMAGE = _image("sentencepiece>=0.2.0")

# ---------------------------------------------------------------------------
# GPUs (Modal 1.x string specs)
# ---------------------------------------------------------------------------
VISION_GPU = "A10G"
STORY_GPU = "A10G"
ILLUSTRATION_GPU = "A100-40GB"  # do not downgrade — see docs/MODELS.md
TTS_GPU = "A10G"
ADAPTATION_GPU = "T4"           # cheapest tier — the model is 1B

# ---------------------------------------------------------------------------
# Per-request timeouts (seconds) — docs/MODAL.md
# ---------------------------------------------------------------------------
VISION_TIMEOUT = 60
STORY_TIMEOUT = 120
ILLUSTRATION_TIMEOUT = 60
TTS_TIMEOUT = 120
ADAPTATION_TIMEOUT = 30

# How long an idle container stays warm before scaling to zero (seconds).
SCALEDOWN_WINDOW = 300

# Container boot budget: model download + load + any warm-up/compile. Modal's
# default (120s) is too short for large weights and torch.compile warm-up, so
# raise it. Illustration gets extra headroom for FLUX's ~24GB first download.
STARTUP_TIMEOUT = 900
ILLUSTRATION_STARTUP_TIMEOUT = 1800
