"""Text-to-speech service abstraction and Edge TTS implementation.

Provider protocol:
    class TTSProvider:
        async def synthesize(
            self, text: str, settings: Settings
        ) -> TTSResult: ...

TTSResult contains audio bytes and word-boundary timing metadata.

Edge TTS requests "WordBoundary" events explicitly and persists
the original timestamp ticks alongside normalized seconds.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from shorts_pipeline.config.settings import Settings
from shorts_pipeline.utils.retry import TransientError, retry_with_backoff

logger = logging.getLogger(__name__)


# ── Data types ─────────────────────────────────────────────────────────────


@dataclass
class WordBoundary:
    """Timing metadata for a single word from TTS."""

    word: str
    offset_seconds: float  # Start time in seconds (from Edge ticks).
    duration_seconds: float  # Duration in seconds.
    offset_ticks: int  # Original Edge tick value for traceability.
    duration_ticks: int  # Original Edge duration tick value.
    end_seconds: float = field(init=False)

    def __post_init__(self) -> None:
        self.end_seconds = self.offset_seconds + self.duration_seconds


@dataclass
class TTSResult:
    """Result of TTS synthesis with actual timing metadata."""

    audio_bytes: bytes
    sample_rate: int = 24000
    duration_seconds: float = 0.0
    word_boundaries: list[WordBoundary] = field(default_factory=list)
    text: str = ""


# ── Provider protocol ──────────────────────────────────────────────────────


class TTSProvider(ABC):
    """Abstract TTS provider. Implementations must return real timing metadata."""

    @abstractmethod
    async def synthesize(self, text: str, settings: Settings) -> TTSResult:
        """Generate speech audio and word-boundary metadata."""
        ...


def get_provider(name: str = "edge") -> TTSProvider:
    """Factory: return a TTS provider instance by name."""
    if name == "edge":
        return EdgeTTSProvider()
    raise ValueError(f"Unknown TTS provider: {name}")


# ── Edge TTS implementation ────────────────────────────────────────────────

EDGE_TICKS_PER_SECOND: int = 10_000_000


class EdgeTTSProvider(TTSProvider):
    """Edge TTS using the edge-tts library with explicit WordBoundary events."""

    async def synthesize(self, text: str, settings: Settings) -> TTSResult:
        """Synthesize via edge-tts, capturing audio and WordBoundary metadata."""
        import edge_tts  # Deferred import — large external dependency.

        voice = settings.tts_voice
        rate = settings.tts_rate
        pitch = settings.tts_pitch
        volume = settings.tts_volume
        timeout = settings.tts_timeout_seconds

        logger.info(
            "Edge TTS: voice=%s rate=%s pitch=%s volume=%s",
            voice,
            rate,
            pitch,
            volume,
        )

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
            boundary="WordBoundary",  # Explicit word-level events.
        )

        audio_chunks: list[bytes] = []
        word_boundaries: list[WordBoundary] = []

        async def _stream() -> TTSResult:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    offset = chunk.get("offset", 0)
                    duration = chunk.get("duration", 0)
                    word_text = chunk.get("text", "")

                    if offset is None or duration is None:
                        logger.warning(
                            "Skipping word boundary with missing offset/duration: %s",
                            chunk,
                        )
                        continue

                    word_boundaries.append(
                        WordBoundary(
                            word=word_text,
                            offset_seconds=offset / EDGE_TICKS_PER_SECOND,
                            duration_seconds=duration / EDGE_TICKS_PER_SECOND,
                            offset_ticks=offset,
                            duration_ticks=duration,
                        )
                    )

            audio_bytes = b"".join(audio_chunks)
            total_duration = word_boundaries[-1].end_seconds if word_boundaries else 0.0

            if not word_boundaries:
                # Captions must be based on provider timestamps, never an MP3
                # byte-size or average-speech estimate.
                raise TransientError("Edge TTS returned no word-boundary metadata")

            previous_end = 0.0
            for boundary in word_boundaries:
                if (
                    boundary.offset_seconds < previous_end
                    or boundary.duration_seconds <= 0
                    or boundary.end_seconds <= boundary.offset_seconds
                ):
                    raise TransientError("Edge TTS returned invalid word-boundary ordering")
                previous_end = boundary.end_seconds
            total_duration = previous_end

            return TTSResult(
                audio_bytes=audio_bytes,
                sample_rate=24000,
                duration_seconds=total_duration,
                word_boundaries=word_boundaries,
                text=text,
            )

        try:
            result = await asyncio.wait_for(
                retry_with_backoff(
                    _stream,
                    max_attempts=2,
                    base_delay=1.0,
                    max_delay=5.0,
                ),
                timeout=timeout,
            )
        except TimeoutError:
            raise TransientError(f"Edge TTS timed out after {timeout:.0f}s") from None

        logger.info(
            "TTS complete: duration=%.2fs words=%d audio_bytes=%d",
            result.duration_seconds,
            len(result.word_boundaries),
            len(result.audio_bytes),
        )

        if not result.word_boundaries and result.audio_bytes:
            logger.warning("TTS audio produced but no word boundaries — captions may use estimates")

        return result


# ── Convenience: save-to-file helper ───────────────────────────────────────


async def synthesize_to_files(
    text: str,
    settings: Settings,
    audio_path: Path,
    metadata_path: Path | None = None,
) -> TTSResult:
    """Synthesize and optionally save the audio and metadata JSON to disk.

    Returns:
        The TTSResult (already available in memory).
    """
    provider = get_provider("edge")
    result = await provider.synthesize(text, settings)

    audio_path.write_bytes(result.audio_bytes)
    logger.info("Saved audio (%d bytes) to %s", len(result.audio_bytes), audio_path)

    if metadata_path:
        metadata = {
            "text": result.text,
            "duration_seconds": result.duration_seconds,
            "word_boundaries": [
                {
                    "word": w.word,
                    "offset_seconds": w.offset_seconds,
                    "duration_seconds": w.duration_seconds,
                    "end_seconds": w.end_seconds,
                    "offset_ticks": w.offset_ticks,
                    "duration_ticks": w.duration_ticks,
                }
                for w in result.word_boundaries
            ],
        }
        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(
            "Saved word-boundary metadata (%d words) to %s",
            len(result.word_boundaries),
            metadata_path,
        )

    return result
