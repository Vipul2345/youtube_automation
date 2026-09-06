"""Pre-upload validation for rendered Shorts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from shorts_pipeline.config.settings import Settings
from shorts_pipeline.utils.retry import TransientError

MIN_UPLOAD_DURATION_SECONDS = 30.0
MAX_UPLOAD_DURATION_SECONDS = 60.0


async def probe_media(path: Path, settings: Settings) -> dict[str, Any]:
    """Run ffprobe and return its JSON output."""
    if not path.is_file():
        raise TransientError(f"Media file not found: {path}")
    command = [
        settings.ffprobe_binary,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=settings.ffprobe_timeout_seconds
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise TransientError("ffprobe timed out during media validation") from None
    if process.returncode:
        message = stderr.decode("utf-8", errors="replace").strip()[:500]
        raise TransientError(f"ffprobe failed: {message}")
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise TransientError(f"ffprobe returned invalid JSON: {exc}") from exc


async def validate_video(path: Path, settings: Settings) -> dict[str, Any]:
    """Validate MP4 dimensions, streams, and duration before upload."""
    data = await probe_media(path, settings)
    streams = data.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not videos:
        raise ValueError("Video validation failed: no video stream")
    if not audios:
        raise ValueError("Video validation failed: no audio stream")
    video = videos[0]
    dimensions = (video.get("width"), video.get("height"))
    expected = (settings.video_width, settings.video_height)
    if dimensions != expected:
        raise ValueError(
            f"Video validation failed: resolution is {dimensions[0]}x{dimensions[1]}, "
            f"expected {expected[0]}x{expected[1]}"
        )
    if video.get("codec_name") != "h264":
        raise ValueError(
            "Video validation failed: expected H.264 video, got "
            f"{video.get('codec_name', 'unknown')}"
        )
    frame_rate = video.get("r_frame_rate", "")
    if frame_rate != f"{settings.video_fps}/1":
        raise ValueError(
            f"Video validation failed: expected {settings.video_fps} FPS, got "
            f"{frame_rate or 'unknown'}"
        )
    audio = audios[0]
    if audio.get("codec_name") != "aac":
        raise ValueError(
            f"Video validation failed: expected AAC audio, got {audio.get('codec_name', 'unknown')}"
        )
    try:
        duration = float(data.get("format", {}).get("duration", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Video validation failed: invalid duration") from exc
    if not MIN_UPLOAD_DURATION_SECONDS <= duration <= MAX_UPLOAD_DURATION_SECONDS:
        raise ValueError(
            f"Video validation failed: duration is {duration:.2f}s, expected "
            f"{MIN_UPLOAD_DURATION_SECONDS:.0f}–{MAX_UPLOAD_DURATION_SECONDS:.0f}s"
        )
    return data
