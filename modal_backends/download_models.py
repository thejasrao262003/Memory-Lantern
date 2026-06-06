"""One-time model warm-up: download every model's weights into the shared Volume.

Run once after deploying (or whenever a model repo changes):

    modal run modal_backends/download_models.py            # all models
    modal run modal_backends/download_models.py --only flux # just one (substring match)

Each inference endpoint mounts the same Volume and points ``HF_HOME`` into it, so
once this has run, cold starts load weights from the Volume instead of
re-downloading them. This runs on a cheap CPU container (downloading is
network/disk-bound — no GPU needed).

Caching is also incorporated lazily in every endpoint (`@modal.enter` downloads
then `weights_volume.commit()`), so this script is an optimisation that moves the
one-time download cost off the first real user request.
"""

from __future__ import annotations

import modal

from modal_backends.shared.modal_config import (
    HF_HOME,
    HF_SECRET,
    VOLUMES,
    weights_volume,
)

app = modal.App("memory-lantern-download")

# Lightweight image: just huggingface_hub (+ the Xet fast-transfer backend) and
# the same cache env the endpoints use, so files land where from_pretrained looks.
download_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("huggingface_hub[hf_xet]>=0.24.0")
    .env(
        {
            "HF_HOME": HF_HOME,
            "HF_HUB_CACHE": f"{HF_HOME}/hub",
            "HF_XET_HIGH_PERFORMANCE": "1",
        }
    )
)

# Repos to cache. For FLUX we skip the standalone single-file weights
# (flux1-schnell.safetensors / ae.safetensors) — the pipeline loads the diffusers
# subfolder format instead, so pulling both would waste ~24GB.
MODELS: list[dict] = [
    {"repo": "openbmb/MiniCPM-V-4.6"},
    {"repo": "openbmb/MiniCPM4.1-8B"},
    {"repo": "openbmb/VoxCPM2"},
    {"repo": "openbmb/MiniCPM5-1B"},
    {
        "repo": "black-forest-labs/FLUX.1-schnell",
        "ignore": ["flux1-schnell.safetensors", "ae.safetensors"],
    },
    {"repo": "SebastianBodza/Flux_Aquarell_Watercolor_v2"},  # watercolour LoRA
]


@app.function(
    image=download_image,
    volumes=VOLUMES,
    secrets=[HF_SECRET],
    timeout=3600,  # FLUX is large; give the whole sweep up to an hour
)
def download(only: str = "") -> list[str]:
    """Download selected (or all) model repos into the shared Volume.

    Args:
        only: optional case-insensitive substring; download only matching repos.

    Returns:
        The list of repo ids that were cached.
    """
    from huggingface_hub import snapshot_download

    weights_volume.reload()
    done: list[str] = []
    for spec in MODELS:
        repo = spec["repo"]
        if only and only.lower() not in repo.lower():
            continue
        print(f"↓  downloading {repo} ...", flush=True)
        path = snapshot_download(repo_id=repo, ignore_patterns=spec.get("ignore"))
        weights_volume.commit()  # checkpoint after each repo
        print(f"✓  cached {repo} -> {path}", flush=True)
        done.append(repo)

    if not done:
        print(f"(no repos matched only={only!r})", flush=True)
    else:
        print(f"done: cached {len(done)} repo(s) into the volume.", flush=True)
    return done


@app.local_entrypoint()
def main(only: str = "") -> None:
    """Trigger the download remotely. Pass --only <substr> to filter."""
    download.remote(only=only)
