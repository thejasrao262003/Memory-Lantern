# SCOPE.md — Project Scope

## In scope for this hackathon submission

These features must be working on submission day (June 15, 2026).

### Core flow
- [ ] Photo upload (1-10 photos, JPEG/PNG)
- [ ] Memory text input (person name, event name, memory paragraph)
- [ ] Full 5-stage pipeline: vision → story → illustration → TTS → PDF
- [ ] Story display as styled HTML in Gradio
- [ ] Illustration gallery (5 images)
- [ ] Audio narration playback
- [ ] PDF download
- [ ] Hardcoded final page in both PDF and narration

### Adaptive feedback loop
- [ ] Caregiver reaction buttons (smiled / unsettled / asleep) per scene
- [ ] Reaction saved to HF Datasets
- [ ] Adaptation weights computed on next generation
- [ ] Story changes based on reaction history (demonstrable in demo)

### Quality / polish
- [ ] Warm, readable Gradio UI (Soft theme + custom CSS)
- [ ] Graceful error handling with user-friendly messages
- [ ] Progress bar during generation
- [ ] Loading state messages ("Painting the illustrations...")

---

## Out of scope — do not build these

These features were considered and explicitly deprioritised.
Do not build them. Do not start them. Finish the in-scope list first.

| Feature | Reason out of scope |
|---|---|
| User authentication / login | 2+ days, not needed for demo |
| Multi-language narration | Multilingual voice matching is complex |
| Voice cloning from uploaded audio | VoxCPM2 can clone but adds UX complexity |
| Multiple storybooks per family | Storage complexity, not needed for demo |
| Sharing / social features | Out of scope for a care tool |
| Mobile app | Web-first, Gradio covers mobile reasonably |
| Real-time generation progress per image | Nice but complex |
| Storybook style selector | Deliberate design choice — one style only |
| Custom final page text | Non-negotiable — see DECISIONS.md ADR-003 |
| Regenerating individual scenes | Full regeneration is simpler and better |
| Direct printing from app | PDF download + home print is sufficient |
| Memory editing after generation | Regenerate from scratch |
| Multiple people per storybook | Keeps the UX focused |

---

## Day-by-day build priority

If you're behind schedule, cut in this order (later items cut first):

**Must ship (non-negotiable):**
1. Full pipeline working end-to-end with all 5 models
2. Audio narration playback
3. PDF download with final page
4. Basic Gradio UI (three tabs)
5. Error handling (no crashes during demo)

**Ship if time allows:**
6. Adaptation loop (caregiver feedback → next story)
7. Custom CSS / warm visual design
8. Reaction history dataframe
9. Progress messages during generation
10. Input validation with helpful error messages

**Cut if pressed:**
11. Regenerate button
12. Detailed story HTML rendering (plain text is acceptable)
13. GitHub Actions CI/CD (manual deploy is fine)
14. Test coverage beyond smoke tests

---

## Definition of "demo ready"

The app is demo-ready when a judge can:
1. Open the HF Space URL
2. Upload one photo, type "Margaret", type a 3-sentence memory
3. Click Generate
4. Within 3 minutes: see 5 illustrated storybook scenes, hear the narration,
   download the PDF
5. See the final page: "Margaret looked out at everything she had made, and it was good."

That is the bar. Everything else is polish.
