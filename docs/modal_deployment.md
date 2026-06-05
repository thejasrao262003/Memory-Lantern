# Deploying the Modal inference backends

Each model runs as its own Modal app with a persistent GPU. Deploys are
**manual** and deliberate — they are intentionally not part of CI.

## 1. Install and authenticate the Modal CLI

```bash
pip install -r requirements-modal.txt   # or: pip install modal
modal setup
```

`modal setup` opens a browser to authenticate and writes a token to
`~/.modal.toml`. You'll reuse the same token id/secret as HF Space secrets.

## 2. Create the shared secrets and cache

The endpoints expect a Modal secret named `huggingface-secret` (for pulling
gated weights) and use a shared volume `memory-lantern-hf-cache` (created
automatically on first deploy).

```bash
modal secret create huggingface-secret HF_TOKEN=hf_xxx
```

## 3. Deploy each backend

```bash
modal deploy modal_backends/vision_endpoint.py
modal deploy modal_backends/story_endpoint.py
modal deploy modal_backends/illustration_endpoint.py
modal deploy modal_backends/tts_endpoint.py
modal deploy modal_backends/adaptation_endpoint.py
```

Each deploy prints the app name and a dashboard URL. The five apps are:

| App name | Model | GPU |
|---|---|---|
| `memory-lantern-vision` | MiniCPM-V 4.6 | A10G |
| `memory-lantern-story` | MiniCPM4.1-8B | A10G |
| `memory-lantern-illustration` | FLUX.1-schnell + LoRA | A100-40GB |
| `memory-lantern-tts` | VoxCPM2 | A10G |
| `memory-lantern-adaptation` | MiniCPM5-1B | T4 |

## 4. Getting the endpoint reference

The Gradio app calls these classes via the Modal SDK using the app name and
class method (e.g. `modal.Cls.from_name("memory-lantern-vision", "MiniCPMVision")`).
No raw URL is needed — the SDK resolves the deployed app by name. Confirm a
deploy is live in the [Modal dashboard](https://modal.com/apps) or with
`modal app list`.

## 5. Set Modal credentials as HF Space secrets

In your Space's **Settings → Variables and secrets**, add:

- `MODAL_TOKEN_ID`
- `MODAL_TOKEN_SECRET`

Both come from `~/.modal.toml` (or `modal token current`). The Gradio app reads
them on startup and logs a warning if they're missing.

## 6. Test each endpoint

```bash
modal run modal_backends/vision_endpoint.py
modal run modal_backends/story_endpoint.py
modal run modal_backends/illustration_endpoint.py
modal run modal_backends/tts_endpoint.py
modal run modal_backends/adaptation_endpoint.py
```

Each module's `@app.local_entrypoint()` prints a confirmation today; once the
`@modal.method` bodies are implemented, extend these entrypoints to send a real
sample request and assert on the response shape.
