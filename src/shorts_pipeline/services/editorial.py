"""Local, deterministic quality gates for generated scripts."""

from __future__ import annotations

import re

from shorts_pipeline.config.settings import Settings
from shorts_pipeline.services.llm import ShortsScript

_ARTIFACTS = re.compile(
    r"(?:as an ai|ignore previous|system message|json schema|instructions?:)", re.I
)
_DIAGNOSES = re.compile(r"\b(?:diagnos(?:is|e|ed)|schizophrenic|psychopath|sociopath)\b", re.I)
_WEAK_HOOK_START = re.compile(
    r"^(?:hey everyone|hello|hi everyone|did you know|here is|here's|today we|in this video)\b",
    re.I,
)


def validate_script(script: ShortsScript, settings: Settings, category: str) -> None:
    """Reject unsafe/unfinished output before TTS, rendering, or publication."""
    text = script.full_script().strip()
    if not script.youtube_title.strip() or len(text) < 80:
        raise ValueError("script must have a usable title and nonempty narration")
    if _ARTIFACTS.search(text) or _ARTIFACTS.search(script.youtube_description):
        raise ValueError("script contains generation or instruction artifacts")
    if _DIAGNOSES.search(text) and "fiction" not in category.casefold():
        raise ValueError("script contains unsupported clinical psychology claims")
    hook_words = script.hook.split()
    if len(hook_words) > 18 or len(script.hook) > 140:
        raise ValueError("hook must be short enough for the first 1–2 seconds")
    if _WEAK_HOOK_START.search(script.hook.strip()):
        raise ValueError("hook must begin with a pattern interrupt, not a generic introduction")
    words = len(text.split())
    if not settings.min_duration_seconds * 1.5 <= words <= settings.max_duration_seconds * 3.5:
        raise ValueError(
            f"narration length ({words} words) is not suitable for the target duration"
        )
    if not script.hook.strip() or not script.cta.strip() or len(script.sections) != 3:
        raise ValueError(
            "script must contain a hook, exactly three narrative beats, and a complete ending"
        )
