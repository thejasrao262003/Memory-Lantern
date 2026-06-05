"""Modal backend: illustration with FLUX.1-schnell + a watercolour LoRA.

Deploy:  modal deploy modal_backends/illustration_endpoint.py
Verify:  modal run modal_backends/illustration_endpoint.py

Renders one storybook illustration per call (512x768 PNG, 4 schnell steps). The
orchestrator calls this five times in parallel. Keeps one warm container because
illustration is on the critical path.
"""

from __future__ import annotations

import io

import modal

from modal_backends.shared.modal_config import (
    HF_SECRET,
    ILLUSTRATION_GPU,
    ILLUSTRATION_IMAGE,
    ILLUSTRATION_STARTUP_TIMEOUT,
    ILLUSTRATION_TIMEOUT,
    SCALEDOWN_WINDOW,
    VOLUMES,
    weights_volume,
)

app = modal.App("memory-lantern-illustration")

MODEL_ID = "black-forest-labs/FLUX.1-schnell"
# Real, most-downloaded FLUX watercolour LoRA (docs named alvdansen/softpastel,
# which 404s — see memory: modal-model-versions-verified).
LORA_ID = "SebastianBodza/Flux_Aquarell_Watercolor_v2"
LORA_SCALE = 0.75  # 0.7–0.8 per docs/MODELS.md
WIDTH, HEIGHT = 512, 768
NUM_STEPS = 4  # schnell default


@app.cls(
    gpu=ILLUSTRATION_GPU,
    image=ILLUSTRATION_IMAGE,
    volumes=VOLUMES,
    secrets=[HF_SECRET],
    timeout=ILLUSTRATION_TIMEOUT,
    scaledown_window=SCALEDOWN_WINDOW,
    startup_timeout=ILLUSTRATION_STARTUP_TIMEOUT,
    min_containers=1,  # keep one warm — illustration is on the critical path
)
class Illustrator:
    """FLUX.1-schnell diffusion pipeline with a watercolour LoRA applied once."""

    @modal.enter()
    def load(self) -> None:
        """Load FLUX.1-schnell and apply the watercolour LoRA (once per container)."""
        import torch
        from diffusers import FluxPipeline

        weights_volume.reload()
        self.pipe = FluxPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
        self.pipe = self.pipe.to("cuda")
        try:
            self.pipe.load_lora_weights(LORA_ID)
            self._lora = True
        except Exception:  # noqa: BLE001 - base model still produces art without the LoRA
            self._lora = False
        weights_volume.commit()

    @modal.method()
    def illustrate(self, prompt: str, scene_number: int, style_period: str) -> bytes:
        """Render one illustration and return PNG bytes (512x768)."""
        import torch

        kwargs = dict(
            prompt=prompt,
            width=WIDTH,
            height=HEIGHT,
            num_inference_steps=NUM_STEPS,
            guidance_scale=0.0,  # schnell is guidance-distilled
            generator=torch.Generator("cuda").manual_seed(scene_number),
        )
        if self._lora:
            kwargs["joint_attention_kwargs"] = {"scale": LORA_SCALE}
        image = self.pipe(**kwargs).images[0]

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()


@app.local_entrypoint()
def main() -> None:
    """Smoke test: render one watercolour illustration and report byte count."""
    png = Illustrator().illustrate.remote(
        "A young woman proudly standing beside a pale blue car on a 1960s "
        "small-town street, her mother smiling beside her, soft watercolour "
        "illustration, warm gentle tones, storybook style, no text",
        scene_number=1,
        style_period="mid-century warm film tones",
    )
    print(f"received {len(png)} bytes of PNG image")
