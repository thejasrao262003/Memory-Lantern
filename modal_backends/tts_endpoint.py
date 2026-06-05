"""Modal backend: narration with VoxCPM2.

Deploy:  modal deploy modal_backends/tts_endpoint.py
Verify:  modal run modal_backends/tts_endpoint.py

Synthesises the full story text in a fixed warm voice and returns WAV bytes.
"""

from __future__ import annotations

import io

import modal

from modal_backends.shared.modal_config import (
    HF_SECRET,
    SCALEDOWN_WINDOW,
    STARTUP_TIMEOUT,
    TTS_GPU,
    TTS_IMAGE,
    TTS_TIMEOUT,
    VOLUMES,
    weights_volume,
)

app = modal.App("memory-lantern-tts")

MODEL_ID = "openbmb/VoxCPM2"

# 🔒 Hardcoded warm voice (docs/DECISIONS.md ADR-007). Not configurable.
DEFAULT_VOICE_DESCRIPTION = (
    "A warm, unhurried voice like a kind grandmother reading a bedtime story, "
    "speaking slowly and clearly, with gentle pauses between sentences."
)


@app.cls(
    gpu=TTS_GPU,
    image=TTS_IMAGE,
    volumes=VOLUMES,
    secrets=[HF_SECRET],
    timeout=TTS_TIMEOUT,
    scaledown_window=SCALEDOWN_WINDOW,
    startup_timeout=STARTUP_TIMEOUT,
)
class Narrator:
    """VoxCPM2 text-to-speech with natural-language voice design."""

    @modal.enter()
    def load(self) -> None:
        """Load VoxCPM2 once per container (cached in the shared volume)."""
        from voxcpm import VoxCPM

        weights_volume.reload()
        self.model = VoxCPM.from_pretrained(MODEL_ID, load_denoiser=False)
        # VoxCPM2 exposes its output sample rate on the inner tts_model.
        self.sample_rate = int(self.model.tts_model.sample_rate)
        weights_volume.commit()

    @modal.method()
    def narrate(self, text: str, voice_description: str = DEFAULT_VOICE_DESCRIPTION) -> bytes:
        """Narrate ``text`` and return WAV bytes.

        VoxCPM2 has no separate voice argument — voice design is expressed by
        prefixing the text with a parenthetical description, e.g.
        ``"(A warm, unhurried voice...) Once upon a time..."``.
        """
        import soundfile as sf

        prompt = f"({voice_description}) {text}"
        wav = self.model.generate(text=prompt, cfg_value=2.0, inference_timesteps=10)
        buf = io.BytesIO()
        sf.write(buf, wav, self.sample_rate, format="WAV")
        return buf.getvalue()


@app.local_entrypoint()
def main() -> None:
    """Smoke test: synthesise one short line and report the byte count."""
    audio = Narrator().narrate.remote(
        "Margaret looked out at everything she had made, and it was good."
    )
    print(f"received {len(audio)} bytes of WAV audio")
