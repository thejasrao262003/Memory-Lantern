# PROMPTS.md — Prompt Templates

These are the exact prompts used for each model.
Do not improvise prompts. Every word here was chosen deliberately.
Changes to prompts require testing before committing.

---

## Vision prompt (MiniCPM-V 4.6)

**Used in:** `app/utils/prompt_builder.py::build_vision_prompt()`

```python
VISION_SYSTEM_PROMPT = """You are analysing old family photographs to help create
a personalised storybook. Extract structured information about the photos.
Return ONLY valid JSON. No prose, no explanation."""

VISION_USER_PROMPT = """Look at these family photographs of {person_name}.

Extract and return this JSON structure:
{{
    "era": "approximate decade, e.g. '1960s' or 'early 1980s'",
    "people_descriptions": [
        "description of person 1 — age, relationship cues, what they're doing",
        "description of person 2..."
    ],
    "locations": [
        "inferred or visible location — e.g. 'hospital corridor', 'seaside town', 'family kitchen'"
    ],
    "emotional_register": "overall emotional tone — e.g. 'joyful and celebratory' or 'quiet and proud'",
    "key_objects": [
        "significant objects — e.g. 'a red car', 'a nurse's uniform', 'a garden full of dahlias'"
    ],
    "style_period": "visual style for illustration — e.g. 'mid-century warm film tones' or '1980s colour photography'"
}}

Focus on details that could anchor a personal story. Be specific about objects and places.
If you cannot determine something, make a reasonable inference from visual cues."""
```

---

## Story generation prompt (MiniCPM4.1-8B)

**Used in:** `app/utils/prompt_builder.py::build_story_prompt()`

```python
STORY_SYSTEM_PROMPT = """You are writing a personalised illustrated storybook
for an elderly person based on their family memory and photos.

Rules you MUST follow:
- Write in second person ("You are standing...", "You remember...")
- Write in present tense
- Write each scene as a warm, flowing paragraph of about 5 to 7 gentle sentences — immersive and unhurried, rich with sensory detail, not just one or two lines
- Ground every scene in specific details from the memory and photos
- Create a gentle emotional arc: ordinary → meaningful → tender peak → quiet reflection → looking back with pride
- Scene 5 must end with the person looking out at their life with quiet satisfaction
- Never mention illness, memory, dementia, hospitals (unless the memory is about being a nurse/doctor)
- Never use the word "remember" — the reader is living it, not recalling it
- Use the person's name at least once per scene
- Names of other people from the memory must appear in the story
- Return ONLY valid JSON — no prose, no markdown, no explanation"""

def build_story_prompt(
    photo_analysis: PhotoAnalysis,
    memory_text: str,
    person_name: str,
    event: str,
    adaptation_weights: dict | None,
) -> str:
    weights_section = ""
    if adaptation_weights:
        strong = [k for k, v in adaptation_weights.items() if v >= 0.7]
        weak = [k for k, v in adaptation_weights.items() if v <= 0.4]
        if strong:
            weights_section = f"""
IMPORTANT — based on how she has responded to previous stories:
- Emphasise these themes more: {', '.join(strong)}
- Reduce these themes: {', '.join(weak) if weak else 'none'}
"""

    return f"""Create a 5-scene personalised storybook for {person_name}.

MEMORY:
{memory_text}

WHAT THIS MEMORY IS ABOUT:
{event}

DETAILS FROM PHOTOS:
- Era: {photo_analysis.era}
- People: {', '.join(photo_analysis.people_descriptions)}
- Locations: {', '.join(photo_analysis.locations)}
- Emotional tone: {photo_analysis.emotional_register}
- Key objects: {', '.join(photo_analysis.key_objects)}
{weights_section}
Return this exact JSON structure:
[
    {{
        "scene_number": 1,
        "text": "a warm paragraph of ~5-7 sentences, second-person present-tense prose",
        "illustration_prompt": "brief visual description for the illustrator",
        "emotional_beat": "one or two words — e.g. 'anticipation' or 'quiet pride'"
    }},
    ...5 scenes total...
]"""
```

---

## Illustration prompt (FLUX.1-schnell)

**Used in:** `app/utils/prompt_builder.py::build_illustration_prompt()`

The story generator returns a basic `illustration_prompt` per scene.
This function enriches it with era-appropriate style modifiers.

```python
ILLUSTRATION_STYLE_SUFFIX = (
    "soft watercolour illustration, warm gentle tones, "
    "storybook style, hand-painted feel, no text, no words"
)

ERA_STYLE_MAP = {
    "1940s": "warm sepia tones, vintage illustration style",
    "1950s": "mid-century pastel palette, clean lines",
    "1960s": "warm amber and cream tones, folk art feeling",
    "1970s": "earthy warm palette, soft focus feel",
    "1980s": "warm colour photography style rendered as illustration",
    "1990s": "bright warm tones, gentle realism",
    "default": "warm golden tones, timeless illustration style",
}

def build_illustration_prompt(
    scene: SceneDict,
    style_period: str,
    era: str,
) -> str:
    era_key = next(
        (k for k in ERA_STYLE_MAP if k in era.lower()),
        "default"
    )
    era_style = ERA_STYLE_MAP[era_key]

    return (
        f"{scene['illustration_prompt']}, "
        f"{era_style}, "
        f"{ILLUSTRATION_STYLE_SUFFIX}"
    )
```

**Example output:**
```
"A woman in her 30s proudly holding car keys outside a small dealership,
her elderly mother standing beside her smiling, 1960s street in background,
warm amber and cream tones, folk art feeling,
soft watercolour illustration, warm gentle tones, storybook style,
hand-painted feel, no text, no words"
```

---

## Adaptation prompt (MiniCPM5-1B)

**Used in:** `app/utils/prompt_builder.py::build_adaptation_prompt()`

```python
ADAPTATION_SYSTEM_PROMPT = """You are analysing caregiver observations about how
an elderly person responded to an illustrated storybook. Return ONLY valid JSON."""

def build_adaptation_prompt(reaction_log: list[dict]) -> str:
    log_text = "\n".join([
        f"Date {r['date']}, Scene {r['scene_number']}: {r['reaction']}"
        + (f" — {r['notes']}" if r.get('notes') else "")
        for r in reaction_log
    ])

    return f"""Based on these caregiver observations over the past week,
determine which story themes to emphasise or reduce:

OBSERVATIONS:
{log_text}

The story themes available are:
- professional_identity (her career, skills, competence)
- family_relationships (children, partner, parents, friends)
- place_and_home (familiar locations, the house, the garden, the street)
- adventure_travel (trips, journeys, new places)
- nature_outdoors (seasons, weather, gardens, the coast)

Return a JSON object with float scores 0.0-1.0 for each theme.
Higher = emphasise this theme more in tomorrow's story.
Base scores on reactions: "smiled" increases the theme, "unsettled" decreases it,
"asleep" slightly decreases it.

Return ONLY this JSON:
{{
    "professional_identity": 0.0,
    "family_relationships": 0.0,
    "place_and_home": 0.0,
    "adventure_travel": 0.0,
    "nature_outdoors": 0.0
}}"""
```

---

## Final page text (hardcoded — not a prompt)

This is NOT generated by any model. It is hardcoded in `app/pdf/builder.py`
and `app/pipeline/narrator.py`.

```python
FINAL_PAGE_TEXT = "{person_name} looked out at everything she had made, and it was good."
```

Do not make this configurable. Do not generate it dynamically.
This line is the emotional conclusion of every story, regardless of content.

---

## Prompt testing

Before committing prompt changes, test with the fixture data in
`tests/fixtures/sample_memory.json`.

Acceptance criteria for story output:
- [ ] Exactly 5 scenes returned
- [ ] All scenes in second person
- [ ] All scenes in present tense
- [ ] Person's name appears in at least 3 scenes
- [ ] Scene 5 ends with a sense of looking back with satisfaction
- [ ] No clinical or negative language
- [ ] Each illustration_prompt is specific enough to generate a meaningful image
- [ ] JSON is valid and deserialises cleanly
