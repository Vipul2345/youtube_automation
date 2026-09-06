"""
Video composition and media assembly service.

Takes TTS audio, ASS subtitles, and stock footage segments; feeds them into
an FFmpeg filtergraph that scales and centre-crops each clip to 1080x1920,
loops/trims to match the required duration, concatenates everything,
normalises audio, and burns the ASS subtitles into the output MP4.
The final file is validated with ffprobe before returning.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from shorts_pipeline.config.settings import Settings
from shorts_pipeline.utils.retry import TransientError

logger = logging.getLogger(__name__)


# ── Data types ────────────────────────────────────────────────────────────


@dataclass
class RenderSegment:
    """A timed visual segment for the renderer."""

    clip_path: Path
    duration: float = 0.0
    seek_point: float = 0.0


# ── Main render entry point ───────────────────────────────────────────────


async def render_video(
    output_path: Path,
    audio_path: Path,
    ass_path: Path,
    segments: list[RenderSegment],
    settings: Settings,
) -> Path:
    """Render the final video by composing audio, captions, and stock clips.

    Args:
        output_path: Destination for the final .mp4.
        audio_path: Path to the TTS audio file.
        ass_path: Path to the ASS subtitle file.
        segments: Ordered visual segments to compose.
        settings: Pipeline settings (binaries, resolutions, etc.).

    Returns:
        The *output_path* on success.

    Raises:
        TransientError: If FFmpeg fails or the output fails ffprobe validation.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not segments:
        raise ValueError("Need at least one RenderSegment")

    width = settings.video_width
    height = settings.video_height
    fps = settings.video_fps

    # ── Build inputs list ──────────────────────────────────────────────
    input_args: list[str] = []
    for seg in segments:
        if not seg.clip_path.exists():
            raise FileNotFoundError(f"Stock clip not found: {seg.clip_path}")
        input_args.extend(["-stream_loop", "-1", "-i", str(seg.clip_path)])

    audio_args = ["-i", str(audio_path)]

    # ── Build video filtergraph ────────────────────────────────────────
    filter_parts: list[str] = []
    concat_inputs: list[str] = []

    for idx, seg in enumerate(segments):
        label = f"v{idx}"
        chain = (
            f"[{idx}:v]"
            f"scale=w={width}:h={height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps={fps},"
            f"trim=duration={seg.duration},"
            f"setpts=PTS-STARTPTS[{label}]"
        )
        filter_parts.append(chain)
        concat_inputs.append(f"[{label}]")

    num_segments = len(segments)
    concat_filter = f"{''.join(concat_inputs)}concat=n={num_segments}:v=1:a=0[v]"
    filter_parts.append(concat_filter)
    video_filtergraph = ";\n".join(filter_parts)

    # ── Build audio filter ─────────────────────────────────────────────
    # Audio is the last input (index = num_segments).
    audio_filtergraph = (
        f"[{num_segments}:a]loudnorm=I=-14:LRA=1:TP=-1.5,"
        f"aformat=sample_rates=44100:channel_layouts=stereo[a]"
    )

    # Combine into one filter_complex.
    full_filtergraph = f"{video_filtergraph}; {audio_filtergraph}"

    # ── Assemble FFmpeg command ────────────────────────────────────────
    cmd = [
        settings.ffmpeg_binary,
        "-y",
        *input_args,
        *audio_args,
        "-filter_complex",
        full_filtergraph,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-preset",
        settings.video_preset,
        "-crf",
        str(settings.video_crf),
        "-profile:v",
        "high",
        "-level",
        "4.2",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-c:a",
        "aac",
        "-b:a",
        f"{settings.audio_bitrate_kbps}k",
        "-ar",
        "44100",
        "-threads",
        str(settings.ffmpeg_threads),
        "-vf",
        f"subtitles={ass_path}",
        str(output_path),
    ]

    logger.info(
        "Rendering %d segments (%.1f s total) -> %s",
        num_segments,
        sum(s.duration for s in segments),
        output_path,
    )
    logger.debug("FFmpeg command: %s", " ".join(cmd))

    # ── Execute ────────────────────────────────────────────────────────
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=settings.ffmpeg_timeout_seconds,
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise TransientError(
            f"FFmpeg timed out after {settings.ffmpeg_timeout_seconds:.0f}s"
        ) from None

    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")[:2000]
        logger.error("FFmpeg stderr:\n%s", stderr_text)
        raise TransientError(f"FFmpeg exited code {proc.returncode} — {stderr_text[:500]}")

    if not output_path.exists() or output_path.stat().st_size < 1024:
        raise TransientError("Rendered output is missing or too small")

    # ── Validate with ffprobe ──────────────────────────────────────────
    await _validate_rendered(output_path, settings)

    logger.info(
        "Render complete: %s (%.1f MB)",
        output_path,
        output_path.stat().st_size / 1_048_576,
    )
    return output_path


# ── Validation ────────────────────────────────────────────────────────────


async def _validate_rendered(path: Path, settings: Settings) -> None:
    """Run ffprobe on *path* and assert expected properties."""
    cmd = [
        settings.ffprobe_binary,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=settings.ffprobe_timeout_seconds,
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise TransientError("ffprobe timed out during validation") from None

    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")[:500]
        raise TransientError(f"ffprobe failed on output: {stderr_text}")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise TransientError(f"ffprobe output not valid JSON: {exc}") from exc

    streams = data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    if not video_streams:
        raise TransientError("Rendered video has no video stream")
    if not audio_streams:
        raise TransientError("Rendered video has no audio stream")

    vs = video_streams[0]
    out_w = vs.get("width", 0)
    out_h = vs.get("height", 0)
    if (out_w, out_h) != (settings.video_width, settings.video_height):
        raise TransientError(
            f"Resolution mismatch: got {out_w}x{out_h}, "
            f"expected {settings.video_width}x{settings.video_height}"
        )

    fmt = data.get("format", {})
    out_duration = float(fmt.get("duration", 0) or 0)
    expected = settings.target_duration_seconds
    tolerance = 2.0
    if abs(out_duration - expected) > tolerance:
        logger.warning(
            "Output duration %.1fs differs from target %.1fs by >%.0fs",
            out_duration,
            expected,
            tolerance,
        )

    logger.info(
        "ffprobe validation passed: %dx%d, %.1f s, %d video/%d audio streams",
        out_w,
        out_h,
        out_duration,
        len(video_streams),
        len(audio_streams),
    )
