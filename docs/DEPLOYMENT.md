# DEPLOYMENT.md — Deployment Guide

## Prerequisites

- Python 3.11+
- Modal account (modal.com) with billing enabled
- Hugging Face account with PRO (for ZeroGPU) or CPU Space
- Git

---

## Step 1 — Local setup

```bash
git clone <your-repo>
cd memory-lantern

# Install HF Space dependencies
pip install -r requirements.txt

# Install Modal backend dependencies (for local testing only)
pip install -r requirements-modal.txt

# Install dev dependencies
pip install -r requirements-dev.txt

# Copy and fill in secrets
cp .env.example .env
# Edit .env with your tokens
```

---

## Step 2 — Create HF Dataset for reaction storage

```python
from huggingface_hub import HfApi

api = HfApi(token="your_hf_token")

# Create private dataset repo
api.create_repo(
    repo_id="your-username/memory-lantern-data",
    repo_type="dataset",
    private=True,
)

# Create initial empty files
api.upload_file(
    path_or_fileobj=b"",
    path_in_repo="reactions/reactions.jsonl",
    repo_id="your-username/memory-lantern-data",
    repo_type="dataset",
)
api.upload_file(
    path_or_fileobj=b"",
    path_in_repo="stories/stories.jsonl",
    repo_id="your-username/memory-lantern-data",
    repo_type="dataset",
)
```

Set `HF_DATASET_REPO=your-username/memory-lantern-data` in your .env.

---

## Step 3 — Set up Modal

```bash
# Install Modal CLI
pip install modal

# Authenticate
modal setup
# Follow the browser prompt to authenticate

# Verify authentication
modal token list
```

---

## Step 4 — Deploy Modal endpoints

Deploy in this order (vision first, adaptation last):

```bash
# Deploy vision endpoint
modal deploy modal_backends/vision_endpoint.py
# Note the endpoint URL printed after deploy

# Deploy story endpoint
modal deploy modal_backends/story_endpoint.py

# Deploy illustration endpoint (takes longer — downloads FLUX.1-schnell ~24GB)
modal deploy modal_backends/illustration_endpoint.py

# Deploy TTS endpoint
modal deploy modal_backends/tts_endpoint.py

# Deploy adaptation endpoint
modal deploy modal_backends/adaptation_endpoint.py
```

**Expected deploy times:**
- vision: ~2 min
- story: ~3 min
- illustration: ~8 min (large model download)
- tts: ~3 min
- adaptation: ~1 min

**Verify deployments:**
```bash
modal app list
# Should show 5 apps with status "deployed"
```

**Test each endpoint:**
```bash
# Test vision
modal run modal_backends/vision_endpoint.py::MiniCPMVision.analyze --images_b64='[]' --person_name='Test'

# Test story (minimal)
modal run modal_backends/story_endpoint.py::StoryGenerator.generate \
    --photo_analysis='{"era":"1960s","people_descriptions":[],"locations":[],"emotional_register":"warm","key_objects":[],"style_period":"mid-century"}' \
    --memory_text='She bought her first car.' \
    --person_name='Margaret' \
    --event='Buying her first car'
```

---

## Step 5 — Get Modal tokens

```bash
# Get your token ID and secret
modal token list

# Or create new tokens
modal token new
```

Store these as:
- `MODAL_TOKEN_ID`
- `MODAL_TOKEN_SECRET`

---

## Step 6 — Deploy HF Space

```bash
# Add HF remote
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/memory-lantern

# Push
git push hf main
```

**HF Space configuration (in Space settings):**

Hardware: CPU Basic (free tier is fine — no GPU needed on Space)

Secrets to add (Settings → Variables and secrets):
```
MODAL_TOKEN_ID          = your_modal_token_id
MODAL_TOKEN_SECRET      = your_modal_token_secret
HF_TOKEN                = your_hf_token
HF_DATASET_REPO         = your-username/memory-lantern-data
```

SDK: Gradio
Python version: 3.11

---

## Step 7 — Add packages.txt for WeasyPrint

Create `packages.txt` in project root:

```
libpango-1.0-0
libcairo2
libgdk-pixbuf2.0-0
libffi-dev
shared-mime-info
```

This ensures WeasyPrint's C dependencies are installed on the Space.

---

## GitHub Actions CI/CD

File: `.github/workflows/deploy.yml`

Triggers on push to `main`. Pushes to HF Spaces automatically.
Does NOT redeploy Modal endpoints (manual step).

```yaml
name: Deploy to HF Spaces

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Push to HF Spaces
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          git config user.email "action@github.com"
          git config user.name "GitHub Action"
          git remote add hf https://USER:${HF_TOKEN}@huggingface.co/spaces/USERNAME/memory-lantern
          git push hf main --force
```

**GitHub secrets to add:**
- `HF_TOKEN` — your Hugging Face token with write access

---

## Environment variables reference

| Variable | Required | Used in | Example |
|---|---|---|---|
| MODAL_TOKEN_ID | Yes | app/pipeline/*.py | tok_xxxxxxx |
| MODAL_TOKEN_SECRET | Yes | app/pipeline/*.py | sk_xxxxxxx |
| HF_TOKEN | Yes | app/storage/*.py | hf_xxxxxxx |
| HF_DATASET_REPO | Yes | app/storage/*.py | username/memory-lantern-data |

For local dev: copy `.env.example` to `.env` and fill in values.
In HF Spaces: add as Space secrets (never in code).
In GitHub Actions: add as repository secrets.

---

## Redeploying after code changes

**If you change HF Space code only (app/):**
```bash
git push hf main
```

**If you change a Modal endpoint:**
```bash
modal deploy modal_backends/affected_endpoint.py
# Then push HF Space if needed
git push hf main
```

**If you change shared Modal config:**
```bash
# Redeploy ALL endpoints
for ep in vision story illustration tts adaptation; do
    modal deploy modal_backends/${ep}_endpoint.py
done
```

---

## Monitoring

```bash
# View live logs for an endpoint
modal app logs memory-lantern-illustration --tail

# Check current GPU usage / costs
modal app list

# Emergency stop (if costs spike)
modal app stop memory-lantern-illustration
```
