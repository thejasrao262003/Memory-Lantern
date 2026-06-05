"""Exception hierarchy for Memory Lantern.

All custom exceptions inherit from :class:`MemoryLanternError`. Pipeline stages
raise :class:`PipelineError` (or a subclass) carrying a *warm, user-facing*
message; the orchestrator catches these, logs the full trace to stderr, and
returns the message to the Gradio layer so the app never crashes mid-demo.

See ``docs/ERRORS.md`` for the full taxonomy and the exact user-facing strings.
"""

from __future__ import annotations

from typing import Optional


class MemoryLanternError(Exception):
    """Base exception. All custom exceptions inherit from this."""


class PipelineError(MemoryLanternError):
    """Raised when a pipeline stage fails. Carries a user-facing message.

    Attributes:
        user_message: A warm, non-technical message safe to show a caregiver.
        stage: The pipeline stage that failed, e.g. ``"photo_analyzer"``.
        original: The underlying exception, if any (kept for logging).
    """

    def __init__(
        self,
        user_message: str,
        stage: str,
        original: Optional[Exception] = None,
    ) -> None:
        self.user_message = user_message
        self.stage = stage
        self.original = original
        super().__init__(user_message)


class ValidationError(MemoryLanternError):
    """Raised when user input fails validation (empty photos, short memory…)."""


class StorageError(MemoryLanternError):
    """Raised when an HF Dataset read/write fails."""


class ModalEndpointError(PipelineError):
    """Raised when a Modal inference endpoint call fails or is unreachable."""
