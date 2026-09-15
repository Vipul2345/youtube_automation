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


_COMMON_STOPWORDS = frozenset({
    "this", "that", "there", "what", "when", "where", "with", "from", "your",
    "they", "them", "their", "will", "would", "about", "could", "have", "been",
    "never", "only", "first", "more", "most", "just", "into", "some", "every",
    "than", "then", "like", "over", "even", "because", "these", "those"
})


def _extract_content_words(text: str) -> set[str]:
    """Extract lowercase alpha words with at least 3 chars excluding common stopwords."""
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return {w for w in words if w not in _COMMON_STOPWORDS}


def validate_script(script: ShortsScript, settings: Settings, category: str) -> None:
    """Reject unsafe, contaminated, or unfinished output before TTS, rendering, or publication."""
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

    # ── Semantic Coherence Quality Gate ────────────────────────────────────
    # Prevent hallucinations where hook contradicts or is completely disjoint
    # from the title and core subject (e.g. Tunguska comet with shadow killer hook).
    hook_terms = _extract_content_words(script.hook)
    title_terms = _extract_content_words(script.youtube_title)
    body_terms = _extract_content_words(" ".join(s.text for s in script.sections))

    shares_title = bool(hook_terms & title_terms)
    body_overlap_count = len(hook_terms & body_terms)

    # If the hook shares no content terms with the title AND fewer than 2 with the body,
    # the LLM hallucinated a disconnected hook from a different context.
    if not shares_title and body_overlap_count < 2:
        raise ValueError(
            "hook lacks semantic coherence with the video title and story body; "
            f"hook terms={sorted(hook_terms)[:5]}, title terms={sorted(title_terms)[:5]}"
        )

    # ── Clean Outro & Terminal Punctuation ─────────────────────────────────
    if not text.endswith((".", "!", "?")):
        raise ValueError("script must terminate cleanly on valid sentence punctuation")
    if text.endswith(("...", "--", ",", ";", ":")):
        raise ValueError("script has trailing punctuation or cut-off fragment artifacts")

