"""Gemini script generation via httpx REST API with JSON schema validation.

Uses the official REST endpoint (not the deprecated google-generativeai SDK).
One request per Short. Output is validated against a strict Pydantic schema.
Malformed JSON triggers safe repair attempts followed by bounded retries.
Recent history is fed into the prompt to avoid topic overlap.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence

import httpx
from pydantic import BaseModel, Field, field_validator

from shorts_pipeline.utils.retry import (
    PermanentError,
    TransientError,
    classify_http_status,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)


# ── Structured output schema ──────────────────────────────────────────────


class ScriptSection(BaseModel):
    """One narrative section within the Short."""

    heading: str = Field(
        ...,
        min_length=1,
        max_length=60,
        description="Short heading for this section (internal use only).",
    )
    text: str = Field(
        ...,
        min_length=10,
        max_length=400,
        description="Spoken script text for this section (10–400 chars).",
    )
    visual_keywords: list[str] = Field(
        ...,
        min_length=1,
        max_length=6,
        description="1–6 search keywords for Pexels footage matching this section.",
    )


class ShortsScript(BaseModel):
    """Complete Shorts generation result from Gemini."""

    hook: str = Field(
        ...,
        min_length=10,
        max_length=140,
        description=(
            "The opening hook (10–140 chars and no more than 18 words), delivered "
            "in the first 1–2 seconds."
        ),
    )
    sections: list[ScriptSection] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly 3 narrative sections with spoken text and visual keywords.",
    )
    cta: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Concise call-to-action delivered at the end.",
    )
    youtube_title: str = Field(
        ...,
        min_length=5,
        max_length=100,
        description="YouTube video title under 100 chars, optimized for Shorts.",
    )
    youtube_description: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="YouTube description (10–500 chars). Include #Shorts hashtag.",
    )
    youtube_tags: list[str] = Field(
        ...,
        min_length=1,
        max_length=15,
        description="1–15 relevant search tags for the video.",
    )
    category: str = Field(
        default="Entertainment",
        description="Category string that maps to a YouTube category ID.",
    )
    source_urls: list[str] = Field(default_factory=list, max_length=8)
    claim_sources: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("youtube_tags")
    @classmethod
    def tags_no_hashtag_prefix(cls, v: Sequence[str]) -> list[str]:
        return [t.removeprefix("#").strip() for t in v]

    def full_script(self) -> str:
        """Return the complete spoken narrative as a clean, properly punctuated string."""
        cta = self.cta.strip()
        hook = self.hook.strip()
        # If the LLM mistakenly appended the opening hook directly into the CTA
        if hook.casefold() in cta.casefold():
            idx = cta.casefold().find(hook.casefold())
            cta = cta[:idx].strip()

        parts = [hook]
        parts.extend(s.text.strip() for s in self.sections)
        if cta:
            parts.append(cta)
        script = " ".join(p for p in parts if p).strip()
        while script.endswith("..."):
            script = script[:-3].strip()
        if not script.endswith((".", "!", "?")):
            script += "."
        return script


# ── Category mapping ──────────────────────────────────────────────────────

# Maps Gemini category strings to YouTube category IDs.
# YouTube category 27 = "Education" is the safe default.
CATEGORY_MAP: dict[str, str] = {
    "science & technology": "27",
    "education": "27",
    "entertainment": "24",
    "music": "10",
    "gaming": "20",
    "howto": "26",
    "news": "25",
    "sports": "17",
    "travel": "19",
}


def map_category(category: str) -> str:
    """Map a returned category string to a YouTube category ID."""
    return CATEGORY_MAP.get(category.strip().lower(), "27")


# ── Prompt construction ────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = """You are an elite YouTube Shorts scriptwriter and retention director.
You write punchy, high-retention short-form video scripts of 40–48 seconds of spoken audio
(approximately 105–125 words).

Your response MUST be valid JSON matching the provided schema. Every field is required.

CORE RETENTION & STRUCTURAL RULES:
1. HOOK INTEGRITY (0–2s): Start with a topic-grounded pattern-interrupt hook (<18 words).
   - If the topic is History/Mysteries, the hook MUST state a real historical anomaly,
     date, place, or event (e.g. "In 1908, a shockwave flattened 80 million trees in Siberia.").
     NEVER use unrelated horror tropes like "Your shadow is trying to kill you".
   - If the topic is Psychology, state a startling behavioral paradox or cognitive bias.
   - The hook MUST directly match the video title and the narrative body.
   - Never start with generic filler ("did you know", "here is", "what if I told you").

2. THREE NARRATIVE BEATS (20–40 words each):
   - Section 1 (Setup): Establish the strange phenomenon or mystery with crisp facts.
   - Section 2 (Twist / Detail): Reveal a bizarre detail or counter-intuitive mechanism.
   - Section 3 (Payoff / Explanation): Deliver the fascinating resolution or true cause.
   - Use short, staccato sentences (under 12 words per sentence) for rapid pacing.

3. SEAMLESS CIRCULAR LOOPING:
   - The final sentence (the CTA/outro) MUST be an open lead-in or bridge clause that
     naturally transitions back into the first words of the opening hook when the video replays.
   - Example:
     If Hook is: "In 1908, a shockwave flattened 80 million trees in Siberia."
     The CTA should end with: "Which is why researchers are still baffled by how..."
     When YouTube replays the Short from 0:00, it sounds like one continuous sentence.
   - CRITICAL: Do NOT copy, repeat, or append the hook text into the CTA!
     The YouTube app automatically replays the video from the beginning.

4. VISUAL B-ROLL KEYWORDS:
   - Provide 2–4 concrete, highly searchable physical keywords per section for stock footage
     (e.g., "siberian taiga aerial", "comet night sky", "fallen pine trees").

5. METADATA:
   - The YouTube title must be under 100 characters and optimized for curiosity and Shorts feed.
   - Include #Shorts in description.
   - Provide 5–12 relevant tags without '#' prefix.

IMPORTANT: Do NOT repeat or substantially overlap topics from the recent history provided."""


def build_generation_prompt(
    topic: str,
    style: str,
    target_duration: float,
    recent_topics: list[str] | None = None,
) -> str:
    """Build the user prompt for Gemini generation."""
    topic_guideline = ""
    if "History" in topic:
        topic_guideline = (
            "CRITICAL: Ground this entirely in a real historical event, expedition, or mystery. "
            "The hook MUST state the specific historical incident, year, or location. "
            "Do NOT use generic horror or unrelated psychological fiction."
        )
    elif "Psychology" in topic:
        topic_guideline = (
            "CRITICAL: Ground this in real cognitive science, perception quirks, or psychology. "
            "The hook must state a real behavioral phenomenon or mental glitch."
        )

    parts = [
        f"Topic area: {topic}",
        f"Style: {style}",
        f"Target duration: {target_duration:.0f} seconds (roughly 110-125 words).",
        "",
        topic_guideline,
        "",
        "Generate a complete YouTube Shorts script and metadata as a JSON object.",
        "Ensure the hook directly connects to the title and story, and make the ending loop "
        "seamlessly back into the opening hook line.",
    ]
    if recent_topics:
        parts.append(
            "\nRECENT TOPICS (DO NOT REPEAT OR SUBSTANTIALLY OVERLAP):\n"
            + "\n".join(f"  - {t}" for t in recent_topics[-20:])
        )
    return "\n".join(parts)


# ── JSON safety repairs ────────────────────────────────────────────────────

_JSON_TRIPLE_BACKTICK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _extract_json(raw: str) -> str:
    """Attempt to extract JSON from markdown code fences if present."""
    stripped = raw.strip()
    match = _JSON_TRIPLE_BACKTICK_RE.search(stripped)
    if match:
        return match.group(1).strip()
    # Check for leading/trailing unquoted text outside braces.
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        return stripped[first_brace : last_brace + 1]
    return stripped


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def _repair_json(raw: str) -> str:
    """Basic JSON repairs before attempting parse."""
    raw = _extract_json(raw)
    # Remove control characters that break json.loads.
    raw = _CONTROL_CHAR_RE.sub("", raw)
    # Replace trailing comma before ] or }.
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    # Remove BOM and other odd whitespace.
    raw = raw.strip().removeprefix("\ufeff").removesuffix("\ufeff")
    return raw


# ── Gemini REST API call ───────────────────────────────────────────────────

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _inline_schema_refs(schema: dict) -> dict:
    """Expand Pydantic's local ``$defs`` references for Gemini's API schema."""
    definitions = schema.get("$defs", {})

    def resolve(value: object) -> object:
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if not isinstance(value, dict):
            return value

        reference = value.get("$ref")
        if reference is not None:
            prefix = "#/$defs/"
            if not isinstance(reference, str) or not reference.startswith(prefix):
                raise ValueError(f"Unsupported schema reference: {reference!r}")
            name = reference.removeprefix(prefix)
            if name not in definitions:
                raise ValueError(f"Unknown schema definition: {name!r}")
            resolved = resolve(definitions[name])
            if not isinstance(resolved, dict):
                raise ValueError(f"Schema definition is not an object: {name!r}")
            resolved.update({key: resolve(item) for key, item in value.items() if key != "$ref"})
            return resolved

        # Gemini REST API rejects Pydantic-generated keys like
        # additionalProperties, title, and default.
        _STRIP_KEYS = frozenset({"$defs", "additionalProperties", "title", "default"})
        return {key: resolve(item) for key, item in value.items() if key not in _STRIP_KEYS}

    result = resolve(schema)
    if not isinstance(result, dict):
        raise ValueError("Response schema must be a JSON object")
    return result


def _build_request_body(
    model: str,
    system_instruction: str,
    user_prompt: str,
    response_schema: dict,
    max_output_tokens: int = 4096,
) -> dict:
    """Build the Gemini generateContent request body using structured output."""
    return {
        "system_instruction": {
            "parts": [{"text": system_instruction}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": max_output_tokens,
            "temperature": 0.7,
            "topP": 0.95,
            "responseMimeType": "application/json",
            "responseSchema": _inline_schema_refs(response_schema),
        },
    }


# ── Main generation function ──────────────────────────────────────────────


async def generate_script(
    api_key: str,
    model: str = "gemini-3.1-flash-lite",
    topic: str = "Everyday science",
    style: str = "Curious, clear, factual, upbeat",
    target_duration: float = 45.0,
    recent_topics: list[str] | None = None,
    max_retries: int = 3,
    http_timeout: float = 30.0,
    max_output_tokens: int = 4096,
) -> ShortsScript:
    """Generate a Shorts script using Gemini with structured output.

    Returns:
        A validated ShortsScript instance.

    Raises:
        PermanentError: For authentication, permission, or schema failures.
        TransientError: If all retries are exhausted on transient errors.
    """
    schema = ShortsScript.model_json_schema()
    user_prompt = build_generation_prompt(topic, style, target_duration, recent_topics)
    request_body = _build_request_body(
        model=model,
        system_instruction=SYSTEM_INSTRUCTION,
        user_prompt=user_prompt,
        response_schema=schema,
        max_output_tokens=max_output_tokens,
    )

    url = f"{GEMINI_API_BASE}/models/{model}:generateContent?key={api_key}"

    async def _do_generate() -> ShortsScript:
        async with httpx.AsyncClient(timeout=httpx.Timeout(http_timeout)) as client:
            response = await client.post(
                url,
                json=request_body,
                headers={"Content-Type": "application/json"},
            )
            classify_http_status(response.status_code, response.text[:500])
            data = response.json()

        # Extract text from Gemini response structure.
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            # Check for blocked content due to safety.
            try:
                reason = data["candidates"][0]["finishReason"]
                ratings = data["candidates"][0].get("safetyRatings", [])
                logger.warning("Gemini blocked: %s | safety: %s", reason, ratings)
            except (KeyError, IndexError):
                pass
            raise PermanentError(
                f"Unexpected Gemini response structure: {exc} — {str(data)[:300]}"
            ) from exc

        # Parse and repair JSON.
        json_str = _repair_json(text)
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise TransientError(f"Malformed JSON from Gemini: {exc}") from exc

        # Validate with Pydantic.
        try:
            return ShortsScript.model_validate(parsed)
        except Exception as exc:
            raise PermanentError(
                f"Schema validation failed: {exc} — keys: {list(parsed.keys())}"
            ) from exc

    return await retry_with_backoff(
        _do_generate,
        max_attempts=max_retries,
        base_delay=2.0,
        max_delay=30.0,
    )
