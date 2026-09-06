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
        max_length=280,
        description="The opening hook (10–280 chars), delivered in the first 1–3 seconds.",
    )
    sections: list[ScriptSection] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="2–5 narrative sections with spoken text and visual keywords.",
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

    @field_validator("youtube_tags")
    @classmethod
    def tags_no_hashtag_prefix(cls, v: Sequence[str]) -> list[str]:
        return [t.removeprefix("#").strip() for t in v]

    def full_script(self) -> str:
        """Return the complete spoken narrative as a single string."""
        parts = [self.hook]
        parts.extend(s.text for s in self.sections)
        parts.append(self.cta)
        return " ".join(parts)


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

SYSTEM_INSTRUCTION = """You are a YouTube Shorts scriptwriter. You generate a single short-form
video script approximately 40–50 seconds of spoken audio (roughly 100–130 words).

Your response MUST be valid JSON matching the provided schema. Every field is required.

Rules:
1. Start with a STRONG, curiosity-driven hook (1–3 seconds).
2. Include exactly 3 useful facts, insights, or narrative beats as separate sections.
3. Each section must provide spoken text AND 1–6 visual search keywords for stock footage.
4. End with a concise call-to-action (like, subscribe, comment).
5. Keep the tone engaging, atmospheric, and advertiser-friendly; avoid graphic violence,
   hateful content, and unsupported claims.
6. The YouTube title must be under 100 characters and optimized for Shorts discovery.
7. Include #Shorts in the description.
8. Provide relevant YouTube tags (no # prefix).
9. Choose one category from: Education, Entertainment, Music, Gaming, Howto, News, Sports, Travel.

IMPORTANT: Do NOT repeat or substantially overlap topics from the recent history provided.
If you cannot generate a sufficiently different topic, indicate an error in the response."""


def build_generation_prompt(
    topic: str,
    style: str,
    target_duration: float,
    recent_topics: list[str] | None = None,
) -> str:
    """Build the user prompt for Gemini generation."""
    parts = [
        f"Topic area: {topic}",
        f"Style: {style}",
        f"Target duration: {target_duration:.0f} seconds.",
        "",
        "Generate a complete YouTube Shorts script and metadata as a JSON object.",
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

        return {key: resolve(item) for key, item in value.items() if key != "$defs"}

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
