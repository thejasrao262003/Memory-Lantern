# PRIZES.md — Hackathon Prize Strategy

## Target prizes

| Prize | Status | What's required |
|---|---|---|
| Backyard AI track prize | Primary target | Best real-world problem solver |
| OpenBMB $10k special award | Primary target | Best use of MiniCPM/VoxCPM models |
| Community Choice | Secondary | Emotional impact, shareability |
| Best Agent badge | Secondary | Genuine adaptive feedback loop |
| Tiny Titan bonus | At risk (see below) | Small models, runs locally |

---

## Why each architectural decision was made for prizes

### OpenBMB $10k

We use FOUR OpenBMB models, each load-bearing:

| Model | Role | Why it's essential |
|---|---|---|
| MiniCPM-V 4.6 | Photo analysis | Removing it = no visual grounding |
| MiniCPM4.1-8B | Story generation | The narrative engine |
| VoxCPM2 | TTS narration | The warm voice IS the experience |
| MiniCPM5-1B | Adaptation agent | Makes the system learn over time |

FLUX.1-schnell is the only non-OpenBMB model, and it's used for illustration only.
Every judging criterion OpenBMB would apply (creative use, model centrality,
technical depth) is satisfied by this stack.

In the submission README and demo video, explicitly name each OpenBMB model
and what it does. Do not bury this.

### Backyard AI track

The target user is a specific, named, real person: a family caregiver of an
elderly parent with early-stage dementia. This is not a generic use case.

The problem is real: narrative memory persists in dementia patients longer
than factual recall. No existing product leverages this. The app does not
treat the condition — it meets the person where they are.

The demo must make the judge think of someone in their own family.

### Community Choice

The final page is the community choice strategy.
It is a single, unchanging, hardcoded sentence:
*"Margaret looked out at everything she had made, and it was good."*

It will be in the demo video. It will make people want to make one for their
own grandmother. That shareability is Community Choice.

### Best Agent

The adaptive feedback loop is a genuine multi-step agent:
1. Observe (caregiver taps reaction)
2. Store (HF Datasets)
3. Reason (MiniCPM5-1B analyses pattern)
4. Act (story weights updated)
5. Repeat (next day)

The agent improves without retraining. It uses a small model for reasoning.
It has a persistent memory (HF Datasets). This satisfies "Best Agent."

### Tiny Titan (at risk)

**We lose Off the Grid because Modal is a cloud inference backend.**
This was a deliberate trade for better latency and simpler GPU management.

We can still argue for Tiny Titan on model size grounds (measured params):
- ≈29.8B total weights across the 5 models — and only **12.86B** of that is the
  four OpenBMB models; the rest (~16.9B) is the FLUX image pipeline
- MiniCPM-V 4.6 at 1.30B — genuinely tiny
- MiniCPM5-1B at 1.08B — ~1 billion parameters on a T4 GPU
- The HF Space itself is CPU-only and runs on free tier

The Tiny Titan argument: "We built something emotionally profound using models
so small they run on a phone — the four language/vision/speech models total
under 13B; the only heavy component is the FLUX image generator (~11.9B
transformer), and we can quantize even that."

---

## Submission checklist

These must all be true at submission time:

- [ ] Demo video is 2-3 minutes, shows the full flow end to end
- [ ] Demo video explicitly plays the audio narration for at least 20 seconds
- [ ] Demo video shows the final page ("looked out at everything")
- [ ] Demo video names all 4 OpenBMB models used
- [ ] Demo video mentions the adaptive feedback loop
- [ ] README has a GIF or screenshot of the storybook output
- [ ] README explicitly lists OpenBMB models with links to HF repos
- [ ] HF Space is public and accessible without login
- [ ] App generates a storybook within 3 minutes (demo requirement)
- [ ] Social media post is live (required for submission)

---

## What NOT to do

- Do not add features after day 8. Polish what's there.
- Do not swap OpenBMB models for non-OpenBMB alternatives.
- Do not remove the final page. It is the emotional peak of the demo.
- Do not make the voice configurable. The warmth of the voice is part of the product.
- Do not pitch this as "a chatbot" or "an assistant." It is a storybook generator.
- Do not mention dementia in the demo video title or thumbnail.
  Use: "Turn family memories into illustrated storybooks"
