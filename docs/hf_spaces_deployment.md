# Deploying the Hugging Face Space

The Gradio app runs on a CPU-tier Space. Inference is delegated to Modal (see
`modal_deployment.md`), so no GPU is needed here.

## 1. Create the Space

1. Go to <https://huggingface.co/new-space>.
2. **SDK:** Gradio.
3. **Hardware:** CPU basic (free tier is sufficient).
4. **Visibility:** your choice — the reaction data lives in a separate private
   dataset regardless.

The Space reads `app/main.py` as its entrypoint (referenced via the symlinked
`README.md` front-matter, or set `app_file: app/main.py` in the Space's README
metadata).

## 2. Configure secrets

In **Settings → Variables and secrets**, add the following secrets:

| Name | Purpose |
|---|---|
| `MODAL_TOKEN_ID` | Authenticates calls to the Modal backends |
| `MODAL_TOKEN_SECRET` | Authenticates calls to the Modal backends |
| `HF_TOKEN` | Read/write access to the private reaction dataset |
| `HF_DATASET_REPO` | e.g. `your-username/memory-lantern-reactions` |

These mirror `.env.example`. The app logs a warning at startup if the Modal
credentials are absent.

## 3. Create the private reaction dataset

```bash
huggingface-cli login   # uses HF_TOKEN
huggingface-cli repo create memory-lantern-reactions --type dataset --private
```

Set `HF_DATASET_REPO` to the resulting `your-username/memory-lantern-reactions`.
`session_store` writes JSONL records here, partitioned by session id.

## 4. Push the code (auto-deploys)

A push to `main` triggers a rebuild. Either push directly to the Space's git
remote, or rely on the GitHub Action in `.github/workflows/deploy.yml`:

```bash
# Direct push
git remote add space https://huggingface.co/spaces/your-username/memory-lantern
git push space main
```

For the GitHub Action, set the repository variable `HF_SPACE` (e.g.
`your-username/memory-lantern`) and the secret `HF_TOKEN`. Every push to `main`
then mirrors the code to the Space. Note: the Action deploys **only** the app —
Modal backends are deployed manually.

## 5. Verify

Open the Space URL. You should see the three tabs ("Create a Story", "Your
Storybook", "How Did It Go?"). Check the Space logs for the
`Modal credentials detected.` line to confirm secrets are wired correctly.
