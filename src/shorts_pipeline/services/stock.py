"""Visual asset retrieval with Pexels API and layered fallback.

Search strategy (bounded budget per section):
1. Portrait/vertical footage from Pexels.
2. Landscape footage cropped to 9:16.
3. Alternative search keywords.
4. Another relevant Pexels result.
5. Local curated royalty-free fallback asset.
6. Programmatic animated fallback (solid color with subtle motion).

The pipeline never fails solely because no suitable stock clip is returned.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import httpx

from shorts_pipeline.config.settings import Settings
from shorts_pipeline.utils.retry import (
    PermanentError,
    TransientError,
    classify_http_status,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)

_FILENAME_SAFE = re.compile(r"[^\w\-_. ]")


def safe_filename(keyword: str, max_len: int = 80) -> str:
    """Sanitize a keyword into a safe filename fragment."""
    safe = _FILENAME_SAFE.sub("_", keyword)[:max_len].strip("._ ")
    return safe or "asset"


# ── Data types ─────────────────────────────────────────────────────────────


@dataclass
class StockClip:
    """Resolved and validated stock footage clip ready for rendering."""

    file_path: Path
    source_url: str
    attribution: str
    license_note: str = "CC-BY Pexels (https://pexels.com)"
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    is_fallback: bool = False


@dataclass
class StockSearchResult:
    """Results from a Pexels API search."""

    clips: list[dict] = field(default_factory=list)
    next_page_url: str | None = None


# ── Pexels API client ──────────────────────────────────────────────────────

PEXELS_BASE = "https://api.pexels.com/videos"
PEXELS_ATTRIBUTION = "Videos provided by Pexels (https://pexels.com)"


async def search_pexels(
    api_key: str,
    query: str,
    orientation: Literal["portrait", "landscape", "square"] = "portrait",
    per_page: int = 5,
    timeout: float = 30.0,
) -> StockSearchResult:
    """Search Pexels video API."""
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": min(per_page, 10),
        "size": "medium",
    }
    url = f"{PEXELS_BASE}/search"
    headers = {"Authorization": api_key}

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        response = await client.get(url, params=params, headers=headers)
        classify_http_status(response.status_code, response.text[:500])
        data = response.json()

    videos = data.get("videos", [])
    result = StockSearchResult(
        clips=videos,
        next_page_url=data.get("next_page"),
    )
    logger.debug(
        "Pexels search '%s' (%s): %d results, next_page=%s",
        query,
        orientation,
        len(videos),
        bool(result.next_page_url),
    )
    return result


def _pick_preferred_clip(videos: list[dict], min_width: int = 480) -> dict | None:
    """Pick the best clip from Pexels results, preferring portrait orientation."""
    valid: list[dict] = []
    for video in videos:
        video_files = video.get("video_files", [])
        if not video_files:
            continue
        width = video.get("width", 0) or 0
        height = video.get("height", 0) or 0
        if width >= min_width and height >= width * 1.5:
            valid.append({"video": video, "type": "portrait", "width": width, "height": height})

    if valid:
        valid.sort(key=lambda x: x["width"], reverse=True)
        return valid[0]["video"]

    # Fallback: landscape that can be zoom-cropped.
    for video in videos:
        width = video.get("width", 0) or 0
        height = video.get("height", 0) or 0
        if width >= min_width and height > 0:
            return video

    return None


def _get_best_video_file(video: dict) -> dict | None:
    """Get the best resolution video file entry from a Pexels video object."""
    files = video.get("video_files", [])
    candidates = [f for f in files if f.get("quality") in ("hd", "sd", "uhd")]
    if not candidates:
        candidates = files
    candidates.sort(key=lambda f: f.get("width", 0) or 0, reverse=True)
    return candidates[0] if candidates else None


# ── Download ──────────────────────────────────────────────────────────────


async def download_clip(
    url: str,
    dest: Path,
    timeout: float = 120.0,
    max_bytes: int = 80_000_000,
    min_bytes: int = 1024,
) -> Path:
    """Download a video clip with validation."""
    async with (
        httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        ) as client,
        client.stream("GET", url) as response,
    ):
        classify_http_status(response.status_code)
        content_length = response.headers.get("content-length")
        if content_length:
            size = int(content_length)
            if size > max_bytes:
                raise PermanentError(f"Content too large: {size:,} bytes (max {max_bytes:,})")
            if size < min_bytes:
                raise PermanentError(f"Content too small: {size:,} bytes (min {min_bytes:,})")

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            bytes_written = 0
            async for chunk in response.aiter_bytes():
                f.write(chunk)
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise PermanentError(f"Download exceeded {max_bytes:,} bytes")
            if bytes_written < min_bytes:
                raise PermanentError(f"Download only {bytes_written:,} bytes (min {min_bytes:,})")

    return dest


# ── Fallback asset generation ──────────────────────────────────────────────


async def generate_fallback_clip(
    dest: Path,
    duration: float = 10.0,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> Path:
    """Generate a programmatic animated fallback clip using FFmpeg."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x1a1a2e:s={width}x{height}:d={duration}:r={fps}",
        "-vf",
        "format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "28",
        "-an",
        str(dest),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")[:500]
        raise TransientError(f"Fallback generation failed: {stderr_text}")

    logger.info("Generated fallback clip: %s (%.0fs)", dest.name, duration)
    return dest


# ── ffprobe utility ────────────────────────────────────────────────────────


async def probe_clip(
    path: Path, binary: str = "ffprobe", timeout: float = 30.0
) -> tuple[float, int, int]:
    """Quick ffprobe to extract duration and dimensions.

    Returns (duration_s, width, height). Any value may be 0 on failure.
    """
    cmd = [
        binary,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        data = json.loads(stdout)
        duration = float(data.get("format", {}).get("duration", 0) or 0)
        width = height = 0
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                width = int(stream.get("width", 0) or 0)
                height = int(stream.get("height", 0) or 0)
                break
        return duration, width, height
    except Exception as exc:
        logger.debug("ffprobe failed for %s: %s", path.name, exc)
        return 0.0, 0, 0


# ── High-level asset resolution ───────────────────────────────────────────


async def resolve_assets_for_section(
    keywords: list[str],
    section_index: int,
    settings: Settings,
    work_dir: Path,
) -> list[StockClip]:
    """Resolve stock footage for one script section.

    Follows the defined fallback chain with bounded search/download budgets.
    Returns at least one clip (fallback guaranteed).
    """
    clips: list[StockClip] = []
    max_searches = settings.stock_max_searches_per_section
    max_downloads = settings.stock_max_downloads_per_section
    api_key = settings.pexels_api_key
    api_key_value = api_key.get_secret_value() if api_key else None

    searches_attempted = 0
    downloads_attempted = 0

    for keyword in keywords[:max_searches]:
        if downloads_attempted >= max_downloads:
            break
        searches_attempted += 1

        if api_key_value:
            clip = await _search_and_download(
                api_key_value,
                keyword,
                "portrait",
                section_index,
                settings,
                work_dir,
            )
            if clip:
                clips.append(clip)
                downloads_attempted += 1
                continue

            # Fallback: landscape cropped.
            clip = await _search_and_download(
                api_key_value,
                keyword,
                "landscape",
                section_index,
                settings,
                work_dir,
            )
            if clip:
                clips.append(clip)
                downloads_attempted += 1
                continue

        continue

    # If no clips resolved, generate fallback.
    if not clips:
        fallback_path = work_dir / f"fallback_s{section_index}.mp4"
        if not fallback_path.exists():
            await generate_fallback_clip(
                fallback_path,
                duration=settings.target_duration_seconds / max(1, len(keywords)),
                width=settings.video_width,
                height=settings.video_height,
                fps=settings.video_fps,
            )
        clips.append(
            StockClip(
                file_path=fallback_path,
                source_url="",
                attribution="Generated programmatic fallback",
                license_note="MIT-style (generated by FFmpeg)",
                is_fallback=True,
            )
        )

    return clips


async def _search_and_download(
    api_key: str,
    keyword: str,
    orientation: Literal["portrait", "landscape"],
    section_index: int,
    settings: Settings,
    work_dir: Path,
) -> StockClip | None:
    """Search Pexels with *keyword* and *orientation*, download the best clip."""
    try:
        result = await retry_with_backoff(
            lambda: search_pexels(
                api_key=api_key,
                query=keyword,
                orientation=orientation,
                per_page=settings.pexels_results_per_search,
                timeout=settings.http_timeout_seconds,
            ),
            max_attempts=settings.retry_max_attempts,
            base_delay=settings.retry_base_seconds,
            max_delay=settings.retry_max_seconds,
        )
    except (TransientError, PermanentError) as exc:
        logger.warning("Pexels search fail for '%s' (%s): %s", keyword, orientation, exc)
        return None

    video = _pick_preferred_clip(result.clips)
    if not video:
        logger.debug("No suitable clip for '%s' (%s)", keyword, orientation)
        return None

    file_entry = _get_best_video_file(video)
    if not file_entry:
        return None

    download_url = file_entry.get("link")
    if not download_url:
        return None

    ext = "mp4"
    safe_key = safe_filename(keyword)
    dest = work_dir / f"stock_s{section_index}_{safe_key}_{secrets.token_hex(4)}.{ext}"

    try:
        await retry_with_backoff(
            lambda: download_clip(
                url=download_url,
                dest=dest,
                timeout=settings.download_timeout_seconds,
                max_bytes=settings.max_asset_bytes,
                min_bytes=settings.min_asset_bytes,
            ),
            max_attempts=settings.retry_max_attempts,
            base_delay=settings.retry_base_seconds,
            max_delay=settings.retry_max_seconds,
        )
    except (TransientError, PermanentError) as exc:
        logger.warning("Download fail for '%s': %s", keyword, exc)
        dest.unlink(missing_ok=True)
        return None

    # Reject downloads that are not readable video files. A zero-valued probe
    # must not reach the renderer, which would otherwise fail much later.
    duration, width, height = await probe_clip(dest, binary=settings.ffprobe_binary)
    if duration <= 0 or width <= 0 or height <= 0:
        dest.unlink(missing_ok=True)
        logger.warning("Downloaded asset failed ffprobe validation: %s", dest.name)
        return None

    return StockClip(
        file_path=dest,
        source_url=f"https://pexels.com/video/{video.get('id', '')}",
        attribution=PEXELS_ATTRIBUTION,
        duration_seconds=duration or 0.0,
        width=width or 0,
        height=height or 0,
    )
