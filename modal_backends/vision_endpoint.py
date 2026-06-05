"""Modal backend: photo analysis with MiniCPM-V 4.6.

Deploy:  modal deploy modal_backends/vision_endpoint.py
Verify:  modal run modal_backends/vision_endpoint.py

Accepts base64-encoded images and returns a JSON-serialisable PhotoAnalysis dict
(era, people_descriptions, locations, emotional_register, key_objects, style_period).
"""

from __future__ import annotations

import base64
import io
import json

import modal

from modal_backends.shared.modal_config import (
    HF_SECRET,
    SCALEDOWN_WINDOW,
    VISION_GPU,
    VISION_IMAGE,
    VISION_TIMEOUT,
    VOLUMES,
    weights_volume,
)

app = modal.App("memory-lantern-vision")

MODEL_ID = "openbmb/MiniCPM-V-4.6"

# Keys of the PhotoAnalysis contract (docs/PIPELINE.md).
_LIST_FIELDS = ("people_descriptions", "locations", "key_objects")
_STR_FIELDS = ("era", "emotional_register", "style_period")


@app.cls(
    gpu=VISION_GPU,
    image=VISION_IMAGE,
    volumes=VOLUMES,
    secrets=[HF_SECRET],
    timeout=VISION_TIMEOUT,
    scaledown_window=SCALEDOWN_WINDOW,
)
class MiniCPMVision:
    """MiniCPM-V 4.6 vision-language model for photo analysis."""

    @modal.enter()
    def load(self) -> None:
        """Load MiniCPM-V 4.6 once per container (cached in the shared volume)."""
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        weights_volume.reload()
        self.processor = AutoProcessor.from_pretrained(MODEL_ID)
        self.model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID, dtype=torch.bfloat16, device_map="cuda"
        ).eval()
        weights_volume.commit()

    @modal.method()
    def analyze(self, images_b64: list[str], person_name: str) -> dict:
        """Analyse uploaded photos and return a PhotoAnalysis dict.

        Args:
            images_b64: base64-encoded JPEG/PNG images.
            person_name: name of the person the memory is about.

        Returns:
            A dict with the six PhotoAnalysis fields.
        """
        from PIL import Image

        from app.utils.prompt_builder import VISION_SYSTEM_PROMPT, build_vision_prompt

        images = []
        for b64 in images_b64:
            try:
                images.append(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"))
            except Exception:  # noqa: BLE001 - skip an unreadable image, keep going
                continue

        question = f"{VISION_SYSTEM_PROMPT}\n\n{build_vision_prompt(person_name)}"
        content = [{"type": "image", "image": img} for img in images]
        content.append({"type": "text", "text": question})
        messages = [{"role": "user", "content": content}]

        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device)
        generated = self.model.generate(**inputs, max_new_tokens=512, do_sample=False)
        trimmed = generated[:, inputs["input_ids"].shape[1]:]
        answer = self.processor.batch_decode(trimmed, skip_special_tokens=True)[0]
        parsed = self._parse(answer)
        # If nothing was extracted, surface the raw output so we can tell a
        # featureless image apart from a prompt/parse problem (visible in logs).
        if not any(parsed.values()):
            print(f"[vision] no fields extracted. raw model output: {answer[:600]!r}", flush=True)
        return parsed

    @staticmethod
    def _parse(text: str) -> dict:
        """Coerce the model's JSON into the strict PhotoAnalysis schema."""
        start, end = text.find("{"), text.rfind("}")
        raw = {}
        if start != -1 and end != -1:
            try:
                raw = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                raw = {}
        result: dict = {}
        for key in _STR_FIELDS:
            result[key] = str(raw.get(key, "") or "")
        for key in _LIST_FIELDS:
            val = raw.get(key, [])
            if isinstance(val, str):
                val = [val]
            result[key] = [str(v) for v in val] if isinstance(val, list) else []
        return result


@app.local_entrypoint()
def main(image: str = "", person_name: str = "Margaret") -> None:
    """Smoke test: analyse a photo.

    Pass a real photo to see meaningful output::

        modal run modal_backends/vision_endpoint.py --image ~/photos/grandma.jpg

    With no ``--image`` it falls back to the repo's 64x64 solid-colour fixture,
    which (correctly) yields empty fields — there is nothing in it to describe.
    Runs locally, so stdlib only (no PIL on the host): read bytes + base64.
    """
    from pathlib import Path

    if image:
        path = Path(image).expanduser()
    else:
        path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample_photo.jpg"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    print(MiniCPMVision().analyze.remote([b64], person_name))
