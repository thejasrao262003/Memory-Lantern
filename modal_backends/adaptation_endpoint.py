"""Modal backend: reaction-log reasoning with MiniCPM5-1B.

Deploy:  modal deploy modal_backends/adaptation_endpoint.py
Verify:  modal run modal_backends/adaptation_endpoint.py

Takes a caregiver reaction log and returns soft theme weights (0.0–1.0) that the
story generator uses to lean into comforting themes.
"""

from __future__ import annotations

import json

import modal

from modal_backends.shared.modal_config import (
    ADAPTATION_GPU,
    ADAPTATION_IMAGE,
    ADAPTATION_TIMEOUT,
    HF_SECRET,
    SCALEDOWN_WINDOW,
    VOLUMES,
    weights_volume,
)

app = modal.App("memory-lantern-adaptation")

# MiniCPM5-1B is preferred; fall back to MiniCPM3-4B if it cannot be loaded.
MODEL_ID = "openbmb/MiniCPM5-1B"
FALLBACK_MODEL_ID = "openbmb/MiniCPM3-4B"

# The five themes the story generator understands (docs/PROMPTS.md).
THEMES = (
    "professional_identity",
    "family_relationships",
    "place_and_home",
    "adventure_travel",
    "nature_outdoors",
)


@app.cls(
    gpu=ADAPTATION_GPU,
    image=ADAPTATION_IMAGE,
    volumes=VOLUMES,
    secrets=[HF_SECRET],
    timeout=ADAPTATION_TIMEOUT,
    scaledown_window=SCALEDOWN_WINDOW,
)
class Adapter:
    """Small reasoning model that turns reaction logs into theme weights."""

    @modal.enter()
    def load(self) -> None:
        """Load the adaptation model once per container (cached in the volume)."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        weights_volume.reload()  # see weights another container may have pulled
        model_id = MODEL_ID
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        except Exception:  # noqa: BLE001 - fall back if the primary is unavailable
            model_id = FALLBACK_MODEL_ID
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)

        self.model = (
            AutoModelForCausalLM.from_pretrained(
                model_id, trust_remote_code=True, dtype=torch.bfloat16
            )
            .eval()
            .cuda()
        )
        self.model_id = model_id
        weights_volume.commit()  # persist freshly downloaded weights

    @modal.method()
    def adapt(self, reaction_log: list[dict]) -> dict:
        """Infer theme weights from a reaction log.

        Args:
            reaction_log: records of ``{date, scene_number, reaction, notes?}``.

        Returns:
            ``{theme: weight}`` for each of :data:`THEMES`, weights in ``[0, 1]``.
        """
        from app.utils.prompt_builder import (
            ADAPTATION_SYSTEM_PROMPT,
            build_adaptation_prompt,
        )

        user_prompt = build_adaptation_prompt(reaction_log)
        messages = [
            {"role": "system", "content": ADAPTATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        text = self._chat(messages, max_new_tokens=256)
        return self._parse_weights(text)

    # -- helpers -----------------------------------------------------------
    def _chat(self, messages: list[dict], max_new_tokens: int, **gen_kwargs) -> str:
        # transformers 5.x: apply_chat_template returns a BatchEncoding dict, so
        # pass return_dict=True and splat it into generate (carries attention_mask).
        enc = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        ).to("cuda")
        gen_kwargs.setdefault("do_sample", False)
        out = self.model.generate(**enc, max_new_tokens=max_new_tokens, **gen_kwargs)
        input_len = enc["input_ids"].shape[1]
        return self.tokenizer.decode(out[0][input_len:], skip_special_tokens=True)

    @staticmethod
    def _parse_weights(text: str) -> dict:
        """Extract the JSON object and clamp to the known themes in [0, 1]."""
        start, end = text.find("{"), text.rfind("}")
        parsed = {}
        if start != -1 and end != -1:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                parsed = {}
        weights: dict = {}
        for theme in THEMES:
            try:
                weights[theme] = max(0.0, min(1.0, float(parsed.get(theme, 0.5))))
            except (TypeError, ValueError):
                weights[theme] = 0.5
        return weights


@app.local_entrypoint()
def main() -> None:
    """Smoke test: send a tiny reaction log and print the weights."""
    sample = [
        {"date": "2026-06-01", "scene_number": 1, "reaction": "smiled", "notes": "her nursing days"},
        {"date": "2026-06-01", "scene_number": 3, "reaction": "unsettled", "notes": ""},
    ]
    print(Adapter().adapt.remote(sample))
