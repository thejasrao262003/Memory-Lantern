# MODAL.md — Modal Endpoint Specifications

Every Modal deployment is documented here.
Do not change GPU tiers, model repos, or method signatures without updating this file.

---

## Deployment overview

| App name | File | GPU | Model | Monthly est. cost |
|---|---|---|---|---|
| memory-lantern-vision | modal_backends/vision_endpoint.py | A10G | MiniCPM-V 4.6 | ~$15-30 |
| memory-lantern-story | modal_backends/story_endpoint.py | A10G | MiniCPM4.1-8B | ~$20-40 |
| memory-lantern-illustration | modal_backends/illustration_endpoint.py | A100-40GB | FLUX.1-schnell | ~$40-80 |
| memory-lantern-tts | modal_backends/tts_endpoint.py | A10G | VoxCPM2 | ~$10-20 |
| memory-lantern-adaptation | modal_backends/adaptation_endpoint.py | T4 | MiniCPM5-1B | ~$5-10 |

Costs are estimates for hackathon-level traffic. Modal bills per second of GPU use.

---

## Shared Modal image

All endpoints use a base Modal image defined in `modal_backends/shared/modal_config.py`.

```python
# modal_backends/shared/modal_config.py

import modal

BASE_IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install([
        "torch>=2.3.0",
        "transformers>=5.7.0",
        "accelerate>=0.30.0",
        "Pillow>=10.0.0",
        "numpy>=1.26.0",
    ])
)

VISION_IMAGE = BASE_IMAGE.pip_install([
    "torchvision",
    "sentencepiece>=0.2.0",
])

STORY_IMAGE = BASE_IMAGE.pip_install([
    "sentencepiece>=0.2.0",
])

ILLUSTRATION_IMAGE = BASE_IMAGE.pip_install([
    "diffusers>=0.30.0",
    "safetensors>=0.4.0",
])

TTS_IMAGE = BASE_IMAGE.pip_install([
    "voxcpm>=0.1.0",
    "soundfile>=0.12.0",
])

ADAPTATION_IMAGE = BASE_IMAGE.pip_install([
    "sentencepiece>=0.2.0",
])

# Timeouts
VISION_TIMEOUT = 60       # seconds
STORY_TIMEOUT = 120
ILLUSTRATION_TIMEOUT = 60
TTS_TIMEOUT = 120
ADAPTATION_TIMEOUT = 30
```

---

## Endpoint 1 — Vision

**File:** `modal_backends/vision_endpoint.py`
**App name:** `memory-lantern-vision`
**GPU:** `modal.gpu.A10G()`
**Container timeout:** 60s
**Keep warm:** 0 (cold start acceptable — ~8s model load)

**Class: MiniCPMVision**

```python
@app.cls(
    gpu=modal.gpu.A10G(),
    image=VISION_IMAGE,
    timeout=VISION_TIMEOUT,
    secrets=[modal.Secret.from_name("huggingface-token")],
)
class MiniCPMVision:

    @modal.enter()
    def load(self):
        """Load MiniCPM-V 4.6 once on container start."""
        ...

    @modal.method()
    def analyze(
        self,
        images_b64: list[str],   # base64-encoded JPEG/PNG strings
        person_name: str,
    ) -> dict:
        """
        Analyze uploaded photos and extract structured metadata.

        Returns dict matching PhotoAnalysis dataclass:
        {
            "era": str,                      # e.g. "1960s"
            "people_descriptions": list[str], # one per detected person
            "locations": list[str],
            "emotional_register": str,        # e.g. "joyful, celebratory"
            "key_objects": list[str],
            "style_period": str,              # for FLUX prompt construction
        }
        """
        ...
```

**Calling from HF Space:**
```python
# app/pipeline/photo_analyzer.py
import modal

MiniCPMVision = modal.Cls.from_name("memory-lantern-vision", "MiniCPMVision")
result = MiniCPMVision().analyze.remote(images_b64=images_b64, person_name=person_name)
```

---

## Endpoint 2 — Story Generation

**File:** `modal_backends/story_endpoint.py`
**App name:** `memory-lantern-story`
**GPU:** `modal.gpu.A10G()`
**Container timeout:** 120s
**Keep warm:** 0

**Class: StoryGenerator**

```python
@app.cls(gpu=modal.gpu.A10G(), image=STORY_IMAGE, timeout=STORY_TIMEOUT)
class StoryGenerator:

    @modal.enter()
    def load(self):
        """Load MiniCPM4.1-8B once on container start."""
        ...

    @modal.method()
    def generate(
        self,
        photo_analysis: dict,       # PhotoAnalysis as dict
        memory_text: str,
        person_name: str,
        event: str,
        adaptation_weights: dict | None = None,
    ) -> list[dict]:
        """
        Generate a 5-scene storybook narrative.

        Returns list of 5 SceneDict:
        [
            {
                "scene_number": int,          # 1-5
                "text": str,                  # 2-4 sentences
                "illustration_prompt": str,   # full FLUX prompt
                "emotional_beat": str,        # e.g. "quiet pride"
            },
            ...
        ]
        """
        ...
```

---

## Endpoint 3 — Illustration

**File:** `modal_backends/illustration_endpoint.py`
**App name:** `memory-lantern-illustration`
**GPU:** `modal.gpu.A100(size="40GB")`  ← Do not downgrade to A10G
**Container timeout:** 60s per image
**Keep warm:** 1  ← Keep one warm container — illustration is on the critical path

**Class: Illustrator**

```python
@app.cls(
    gpu=modal.gpu.A100(size="40GB"),
    image=ILLUSTRATION_IMAGE,
    timeout=ILLUSTRATION_TIMEOUT,
    keep_warm=1,
)
class Illustrator:

    @modal.enter()
    def load(self):
        """
        Load FLUX.1-schnell pipeline AND watercolour LoRA.
        LoRA is applied once here, not per request.
        """
        ...

    @modal.method()
    def illustrate(
        self,
        prompt: str,      # Full enriched prompt from prompt_builder
        scene_number: int,
        style_period: str,
    ) -> bytes:
        """
        Generate one storybook illustration.
        Returns PNG bytes.
        Resolution: 512x768 (portrait).
        Inference steps: 4 (schnell default).
        """
        ...
```

**Note on parallelism:**
The orchestrator calls `Illustrator().illustrate.remote(...)` five times
using `modal.functions.gather()` or `concurrent.futures.ThreadPoolExecutor`.
Modal handles the concurrent container allocation automatically.

```python
# app/pipeline/illustrator.py — pattern to follow
import modal
from concurrent.futures import ThreadPoolExecutor

Illustrator = modal.Cls.from_name("memory-lantern-illustration", "Illustrator")

def generate_illustrations(scenes, style_period):
    illustrator = Illustrator()
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(
                illustrator.illustrate.remote,
                scene["illustration_prompt"],
                scene["scene_number"],
                style_period
            )
            for scene in scenes
        ]
        return [f.result() for f in futures]
```

---

## Endpoint 4 — TTS Narration

**File:** `modal_backends/tts_endpoint.py`
**App name:** `memory-lantern-tts`
**GPU:** `modal.gpu.A10G()`
**Container timeout:** 120s
**Keep warm:** 0

**Class: Narrator**

```python
@app.cls(gpu=modal.gpu.A10G(), image=TTS_IMAGE, timeout=TTS_TIMEOUT)
class Narrator:

    @modal.enter()
    def load(self):
        """Load VoxCPM2 once on container start."""
        ...

    @modal.method()
    def narrate(
        self,
        text: str,
        voice_description: str = (
            "A warm, unhurried voice like a kind grandmother reading a "
            "bedtime story, speaking slowly and clearly, with gentle "
            "pauses between sentences."
        ),
    ) -> bytes:
        """
        Narrate the full storybook text.
        Returns WAV bytes at 48kHz.
        """
        ...
```

---

## Endpoint 5 — Adaptation Agent

**File:** `modal_backends/adaptation_endpoint.py`
**App name:** `memory-lantern-adaptation`
**GPU:** `modal.gpu.T4()`  ← Cheapest tier — model is 1B params
**Container timeout:** 30s
**Keep warm:** 0

**Class: Adapter**

```python
@app.cls(gpu=modal.gpu.T4(), image=ADAPTATION_IMAGE, timeout=ADAPTATION_TIMEOUT)
class Adapter:

    @modal.enter()
    def load(self):
        """Load MiniCPM5-1B once on container start."""
        ...

    @modal.method()
    def adapt(
        self,
        reaction_log: list[dict],
    ) -> dict[str, float]:
        """
        Analyse reaction history and return story weighting.

        Input reaction_log format:
        [
            {
                "date": "2026-06-10",
                "scene_number": 3,
                "reaction": "smiled",   # "smiled" | "unsettled" | "asleep"
                "notes": "optional free text"
            },
            ...
        ]

        Returns weights dict, values 0.0-1.0:
        {
            "professional_identity": 0.85,
            "family_relationships": 0.70,
            "place_and_home": 0.60,
            "adventure_travel": 0.30,
            "nature_outdoors": 0.45,
        }
        """
        ...
```

---

## Deploy commands

Run these from the project root after `modal setup`:

```bash
# Deploy all endpoints
modal deploy modal_backends/vision_endpoint.py
modal deploy modal_backends/story_endpoint.py
modal deploy modal_backends/illustration_endpoint.py
modal deploy modal_backends/tts_endpoint.py
modal deploy modal_backends/adaptation_endpoint.py

# Test an endpoint locally
modal run modal_backends/vision_endpoint.py::MiniCPMVision.analyze

# Check deployment status
modal app list

# View logs
modal app logs memory-lantern-vision
```

---

## Authentication from HF Space

The HF Space calls Modal endpoints using the Modal client.
Tokens are injected as environment variables.

```python
# Pattern used in every app/pipeline/*.py file
import os
import modal

# This is called once at app startup in app/main.py
def init_modal():
    token_id = os.environ.get("MODAL_TOKEN_ID")
    token_secret = os.environ.get("MODAL_TOKEN_SECRET")
    if not token_id or not token_secret:
        print("WARNING: Modal tokens not set. Inference will fail.")
    # Modal client auto-reads these env vars
```

---

## Cold start times (approximate)

| Endpoint | Model load time | First request latency |
|---|---|---|
| Vision | ~8s | ~12s |
| Story | ~15s | ~45s |
| Illustration | ~25s | ~40s (keep_warm=1 eliminates this) |
| TTS | ~10s | ~15s |
| Adaptation | ~3s | ~5s |

Cold starts only happen after ~5 minutes of inactivity.
The illustration endpoint has keep_warm=1 to eliminate its cold start.
