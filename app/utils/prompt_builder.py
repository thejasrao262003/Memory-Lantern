"""Prompt construction for each model in the pipeline.

These functions are pure: they turn structured data into the prompt strings sent
to the Modal endpoints. Keeping them here (rather than inside the pipeline steps)
makes the prompts easy to unit-test and tune without touching inference code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.pipeline.orchestrator import SceneDict
    from app.pipeline.photo_analyzer import PhotoAnalysis

# Style modifiers appended to illustration prompts to keep a consistent,
# gentle, dementia-friendly watercolour look across every scene.
_BASE_ILLUSTRATION_STYLE = (
    "soft watercolour illustration, gentle warm palette, hand-painted, "
    "storybook art, calm and comforting, no text"
)

# ---------------------------------------------------------------------------
# System prompts (used by the Modal endpoints alongside the user prompts below).
# Source of truth: docs/PROMPTS.md.
# ---------------------------------------------------------------------------
VISION_SYSTEM_PROMPT = (
    "You are analysing old family photographs to help create a personalised "
    "storybook. Extract structured information about the photos. Return ONLY "
    "valid JSON. No prose, no explanation."
)

STORY_SYSTEM_PROMPT = (
    "You are writing a personalised illustrated storybook for an elderly person "
    "based on their family memory and photos.\n\n"
    "Rules you MUST follow:\n"
    "- Write in second person (\"You are standing...\", \"You remember...\")\n"
    "- Write in present tense\n"
    "- Write each scene as a warm, flowing paragraph of about 5 to 7 gentle "
    "sentences — immersive and unhurried, rich with sensory detail (what is "
    "seen, heard, felt), not just one or two lines\n"
    "- Ground every scene in specific details from the memory and photos\n"
    "- Create a gentle emotional arc: ordinary -> meaningful -> tender peak -> "
    "quiet reflection -> looking back with pride\n"
    "- Scene 5 must end with the person looking out at their life with quiet "
    "satisfaction\n"
    "- Never mention illness, memory, dementia, hospitals (unless the memory is "
    "about being a nurse/doctor)\n"
    "- Never use the word \"remember\" — the reader is living it, not recalling it\n"
    "- Use the person's name at least once per scene\n"
    "- Names of other people from the memory must appear in the story\n"
    "- Return ONLY valid JSON — no prose, no markdown, no explanation"
)

ADAPTATION_SYSTEM_PROMPT = (
    "You are analysing caregiver observations about how an elderly person "
    "responded to an illustrated storybook. Return ONLY valid JSON."
)


def build_vision_prompt(person_name: str) -> str:
    """Build the system prompt for the vision model.

    Instructs the model to return structured visual context focused on the
    named person and the era/setting of the photos.
    """
    return (
        "You are a gentle, observant assistant helping to recreate a cherished "
        f"memory involving {person_name}. Look carefully at the photograph(s) and "
        "describe them as structured JSON with these fields: era, "
        "people_descriptions (a list), locations (a list), emotional_register, "
        "key_objects (a list), and style_period. Be specific about the time "
        "period and visual style so an illustrator could recreate the scene. "
        "Describe people warmly and respectfully."
    )


def build_story_prompt(
    photo_analysis: "PhotoAnalysis",
    memory_text: str,
    person_name: str,
    event: str,
    adaptation_weights: Optional[dict] = None,
) -> str:
    """Build the full story-generation prompt.

    Combines the photo analysis, the caregiver's written memory, and any
    adaptation weights (as *soft* thematic guidance) into a single instruction
    for the story model.
    """
    parts: list[str] = [
        "You are writing a warm, simple five-scene illustrated storybook for an "
        "elderly reader with early-stage dementia. Use clear, unhurried language, "
        "short sentences, and a comforting, affirming tone. Write in the third "
        f"person about {person_name}.",
        "",
        f"The memory is about: {event}.",
        "",
        "In the caregiver's own words:",
        f'"{memory_text.strip()}"',
        "",
        "Visual context from the photographs:",
        f"- Era: {photo_analysis.era}",
        f"- People: {', '.join(photo_analysis.people_descriptions) or 'unspecified'}",
        f"- Locations: {', '.join(photo_analysis.locations) or 'unspecified'}",
        f"- Mood: {photo_analysis.emotional_register}",
        f"- Key objects: {', '.join(photo_analysis.key_objects) or 'unspecified'}",
        f"- Visual style: {photo_analysis.style_period}",
    ]

    if adaptation_weights:
        ranked = sorted(adaptation_weights.items(), key=lambda kv: kv[1], reverse=True)
        emphasis = ", ".join(f"{theme} ({weight:.1f})" for theme, weight in ranked)
        parts += [
            "",
            "Gently emphasise the themes that have brought comfort before "
            f"(soft preference, not a strict rule): {emphasis}.",
        ]

    parts += [
        "",
        "Return exactly five scenes. For each scene provide: scene_number, text, "
        "illustration_prompt, and emotional_beat. The illustration_prompt should "
        "describe the scene visually in the era and style noted above.",
    ]
    return "\n".join(parts)


def build_illustration_prompt(
    scene: "SceneDict",
    style_period: str,
    era: str,
) -> str:
    """Enrich a scene's illustration prompt with era and style modifiers.

    Args:
        scene: The scene whose ``illustration_prompt`` should be enriched.
        style_period: Visual style cue, e.g. "1950s Kodachrome".
        era: Time period, e.g. "late 1950s".

    Returns:
        A single FLUX-ready prompt string.
    """
    base = scene.get("illustration_prompt", "").strip()
    modifiers = [base, f"set in {era}", style_period, _BASE_ILLUSTRATION_STYLE]
    return ", ".join(part for part in modifiers if part)


def build_adaptation_prompt(reaction_log: list[dict]) -> str:
    """Format the reaction log into a prompt for the adaptation model.

    The model is asked to infer which themes bring comfort and return theme
    weights in ``[0, 1]``.
    """
    if not reaction_log:
        lines = ["(no reactions logged yet)"]
    else:
        lines = [
            f"- Scene {r.get('scene_number', '?')}: {r.get('reaction', 'unknown')} "
            f"(on {r.get('date', 'unknown date')})"
            for r in reaction_log
        ]
    log_block = "\n".join(lines)
    return (
        "You are helping personalise gentle storybooks for someone with dementia. "
        "Below is a log of how they reacted to past story scenes. Infer which "
        "themes bring comfort and recognition, and which seem unsettling. Return a "
        "JSON object mapping each theme (professional_identity, family, place, "
        "adventure) to a weight between 0 and 1, where higher means emphasise more.\n\n"
        f"Reaction log:\n{log_block}"
    )
