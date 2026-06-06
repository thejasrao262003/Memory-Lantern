"""Modal backend: story generation with MiniCPM4.1-8B.

Deploy:  modal deploy modal_backends/story_endpoint.py
Verify:  modal run modal_backends/story_endpoint.py

Turns the photo analysis + written memory (+ optional adaptation weights) into a
five-scene storybook as a list of SceneDicts.
"""

from __future__ import annotations

import json

import modal

from modal_backends.shared.modal_config import (
    HF_SECRET,
    SCALEDOWN_WINDOW,
    STORY_GPU,
    STORY_IMAGE,
    STORY_TIMEOUT,
    VOLUMES,
    weights_volume,
)

app = modal.App("memory-lantern-story")

MODEL_ID = "openbmb/MiniCPM4.1-8B"


@app.cls(
    gpu=STORY_GPU,
    image=STORY_IMAGE,
    volumes=VOLUMES,
    secrets=[HF_SECRET],
    timeout=STORY_TIMEOUT,
    scaledown_window=SCALEDOWN_WINDOW,
)
class StoryGenerator:
    """MiniCPM4.1-8B language model for five-scene story generation."""

    @modal.enter()
    def load(self) -> None:
        """Load MiniCPM4.1-8B once per container (cached in the shared volume)."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        weights_volume.reload()
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        self.model = (
            AutoModelForCausalLM.from_pretrained(
                MODEL_ID, trust_remote_code=True, dtype=torch.bfloat16
            )
            .eval()
            .cuda()
        )
        weights_volume.commit()

    @modal.method()
    def generate(
        self,
        photo_analysis: dict,
        memory_text: str,
        person_name: str,
        event: str,
        adaptation_weights: dict | None = None,
    ) -> list[dict]:
        """Generate exactly five scene dicts.

        Each scene has ``scene_number``, ``text``, ``illustration_prompt``,
        ``emotional_beat``.
        """
        from app.pipeline.photo_analyzer import PhotoAnalysis
        from app.utils.prompt_builder import STORY_SYSTEM_PROMPT, build_story_prompt

        analysis = PhotoAnalysis(**{
            k: photo_analysis.get(k, [] if k.endswith("s") and k != "emotional_register" else "")
            for k in (
                "era", "people_descriptions", "locations",
                "emotional_register", "key_objects", "style_period",
            )
        })
        user_prompt = build_story_prompt(
            photo_analysis=analysis,
            memory_text=memory_text,
            person_name=person_name,
            event=event,
            adaptation_weights=adaptation_weights,
        )
        messages = [
            {"role": "system", "content": STORY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        text = self._chat(
            messages, max_new_tokens=3072, do_sample=True, temperature=0.7, top_p=0.9
        )
        scenes = self._parse_scenes(text)
        # Surface the raw output when nothing parsed, so we can tell prose/reasoning
        # apart from truncation or an empty generation (visible in logs).
        if not any(s["text"] for s in scenes):
            print(f"[story] no scenes parsed. raw output (first 1500 chars): {text[:1500]!r}", flush=True)
        return scenes

    # -- helpers -----------------------------------------------------------
    def _chat(self, messages: list[dict], max_new_tokens: int, **gen_kwargs) -> str:
        # transformers 5.x: apply_chat_template returns a BatchEncoding dict, so
        # pass return_dict=True and splat it into generate (carries attention_mask).
        # MiniCPM4.1-8B is a reasoning model; disable the <think> trace so it
        # emits the JSON answer directly (docs/model card: enable_thinking=False).
        enc = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
            enable_thinking=False,
        ).to("cuda")
        gen_kwargs.setdefault("do_sample", False)
        out = self.model.generate(**enc, max_new_tokens=max_new_tokens, **gen_kwargs)
        input_len = enc["input_ids"].shape[1]
        return self.tokenizer.decode(out[0][input_len:], skip_special_tokens=True)

    @staticmethod
    def _parse_scenes(text: str) -> list[dict]:
        """Extract the JSON array and normalise to exactly five scene dicts."""
        start, end = text.find("["), text.rfind("]")
        scenes: list = []
        if start != -1 and end != -1:
            try:
                scenes = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                scenes = []

        normalised: list[dict] = []
        for i, scene in enumerate(scenes[:5]):
            if not isinstance(scene, dict):
                continue
            normalised.append(
                {
                    "scene_number": int(scene.get("scene_number", i + 1)),
                    "text": str(scene.get("text", "")).strip(),
                    "illustration_prompt": str(scene.get("illustration_prompt", "")).strip(),
                    "emotional_beat": str(scene.get("emotional_beat", "")).strip(),
                }
            )
        # Defensive: pad to five so downstream (illustration/PDF) always has five.
        while len(normalised) < 5:
            n = len(normalised) + 1
            normalised.append(
                {
                    "scene_number": n,
                    "text": "",
                    "illustration_prompt": "",
                    "emotional_beat": "",
                }
            )
        return normalised


@app.local_entrypoint()
def main() -> None:
    """Smoke test with a minimal photo analysis + memory."""
    analysis = {
        "era": "1960s",
        "people_descriptions": ["a young woman", "her mother"],
        "locations": ["a small-town street"],
        "emotional_register": "joyful and proud",
        "key_objects": ["a pale blue car"],
        "style_period": "mid-century warm film tones",
    }
    scenes = StoryGenerator().generate.remote(
        analysis, "She saved for three years to buy her first car.", "Margaret", "Buying her first car"
    )
    for s in scenes:
        print(s["scene_number"], "-", s["text"][:80])
