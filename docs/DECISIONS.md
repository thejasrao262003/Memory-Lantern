# DECISIONS.md — Architecture Decision Log

Every significant architectural decision is recorded here with its rationale.
Before changing any of these decisions, read the rationale.
If you disagree with a decision, add a new entry — don't silently change the code.

---

## ADR-001: Modal for inference, not ZeroGPU

**Decision:** Use Modal GPU endpoints for all model inference.

**Rationale:**
- ZeroGPU has a 60-second timeout per `@spaces.GPU` decorated function.
  Generating 5 FLUX illustrations (even in parallel) risks hitting this limit.
- ZeroGPU requires sequential model loading on a shared GPU — complex to manage
  for 4+ models of different sizes.
- Modal allows each model to be a persistent, independently-scaled service.
- Modal GPU cold starts are acceptable (<30s) for a hackathon demo.

**Trade-off accepted:**
- Loses "Off the Grid" badge (modal calls are cloud API calls).
- Adds Modal billing costs (~$5-10 for hackathon traffic).
- Adds Modal token management complexity.

**Status:** Final. Do not revert.

---

## ADR-002: Four OpenBMB models, one non-OpenBMB

**Decision:** Use MiniCPM-V 4.6, MiniCPM4.1-8B, VoxCPM2, and MiniCPM5-1B
from OpenBMB. Use FLUX.1-schnell (Black Forest Labs) for illustration only.

**Rationale:**
- OpenBMB offers a $10k special prize for best use of their models.
- All four OpenBMB models are load-bearing — removing any one collapses a
  core feature.
- FLUX.1-schnell has no OpenBMB equivalent at comparable quality.
  The illustration quality is critical to the emotional impact.
  Using an inferior illustration model to stay 100% OpenBMB would hurt the
  track prize chances more than it helps the OpenBMB prize chances.

**Trade-off accepted:**
- FLUX.1-schnell on A100-40GB is the most expensive Modal deployment.
- The OpenBMB judges may note it. We should acknowledge it proactively:
  "FLUX.1-schnell is our only non-OpenBMB model, used for illustration
  quality that the emotional experience requires."

**Status:** Final. Do not substitute illustration model without this level of review.

---

## ADR-003: Hardcoded final page text

**Decision:** The final page text is always:
`"{person_name} looked out at everything she had made, and it was good."`

**Rationale:**
- This is the emotional apex of the demo. It must be reliable and consistent.
- AI-generated endings are inconsistent — sometimes beautiful, sometimes flat.
- The specific wording ("looked out", "everything she had made", "it was good")
  was chosen deliberately: it echoes biblical language without being religious,
  it places the person as active creator of their own life, it is simple enough
  to land even on a second listen.
- Configurability would dilute it. Every storybook ends the same way.
  That's the point.

**Trade-off accepted:**
- Male/non-binary subjects: the pronoun is wrong. We use "she" universally
  for the hackathon demo. A production version would need pronoun handling.

**Status:** Final. Do not generate dynamically. Do not parameterise.

---

## ADR-004: No user authentication

**Decision:** No login, no user accounts. Session IDs are anonymous UUIDs.

**Rationale:**
- This is a hackathon demo. Authentication is 2+ days of engineering.
- The reaction log is keyed by UUID — not linkable to PII without external data.
- If the Space URL is shared, someone could read another session's reactions.
  For a dementia care app this is a privacy risk. We acknowledge this and
  note that a production version would require authentication.

**Trade-off accepted:**
- Privacy risk for shared URLs.
- No persistent user identity across devices.
- Adaptation loop requires same browser session to accumulate history.

**Status:** Acceptable for hackathon. Must be addressed before any real-world use.

---

## ADR-005: Parallel illustration generation

**Decision:** Generate all 5 illustrations concurrently using ThreadPoolExecutor.

**Rationale:**
- Sequential FLUX generation: ~15s × 5 = ~75 seconds.
- Parallel FLUX generation: ~15-20 seconds total.
- Modal handles concurrent container allocation automatically.
- The 60-second total generation target requires parallel illustration.

**Trade-off accepted:**
- Slightly higher cost (5 container-seconds vs 1 × 5 iterations).
- Ordering must be preserved — results are collected and sorted by scene_number.

**Status:** Final. Do not change to sequential.

---

## ADR-006: HF Datasets for reaction storage, not a database

**Decision:** Use a private HF Dataset (JSONL files) for reaction log storage.

**Rationale:**
- Zero additional infrastructure cost or setup.
- HF token is already required for the Space.
- Reaction write frequency is very low (once per session per day).
- For a hackathon, a real database (Postgres, Supabase, etc.) adds setup time
  and cost with no meaningful benefit.

**Trade-off accepted:**
- Race conditions under concurrent writes (see STORAGE.md).
- Slightly slower read/write than a database.
- JSONL append pattern is fragile at scale.

**Status:** Acceptable for hackathon. Replace with real storage before production.

---

## ADR-007: Warm voice is not configurable

**Decision:** The VoxCPM2 voice description is hardcoded and cannot be changed by users.

**Rationale:**
- The warmth and pace of the voice is part of the therapeutic design.
- Giving users a "cold narrator" option would undermine the product.
- VoxCPM2 voice design via natural language is new — we showcase it by
  making a deliberate, opinionated choice, not by hiding it behind a dropdown.

**Trade-off accepted:**
- Users who want a different voice cannot get one.
- Non-English families will get an accented English narrator (VoxCPM2 supports
  30 languages but we hardcode the English description).

**Status:** Final for hackathon. Multilingual voice matching is a future feature.
