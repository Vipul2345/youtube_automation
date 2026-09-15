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
    total_duration: float | None = None,
) -> Path:
    """Render the final video by composing audio, captions, and stock clips.

    Args:
        output_path: Destination for the final .mp4.
        audio_path: Path to the TTS audio file.
        ass_path: Path to the ASS subtitle file.
        segments: Ordered visual segments to compose.
        settings: Pipeline settings (binaries, resolutions, etc.).
        total_duration: Explicit render duration in seconds (defaults to sum of segment durations).

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
    target_render_duration = total_duration or sum(s.duration for s in segments)

    # ── Build inputs list ──────────────────────────────────────────────
    # Deduplicate clip file inputs to avoid redundant decoders and file handle leaks
    unique_clips: list[Path] = []
    clip_to_input_idx: dict[Path, int] = {}
    input_args: list[str] = []

    for seg in segments:
        if not seg.clip_path.exists():
            raise FileNotFoundError(f"Stock clip not found: {seg.clip_path}")
        if seg.clip_path not in clip_to_input_idx:
            clip_to_input_idx[seg.clip_path] = len(unique_clips)
            unique_clips.append(seg.clip_path)
            input_args.extend(["-stream_loop", "-1", "-i", str(seg.clip_path)])

    audio_input_idx = len(unique_clips)
    audio_args = ["-i", str(audio_path)]

    # ── Build video filtergraph ────────────────────────────────────────
    filter_parts: list[str] = []
    concat_inputs: list[str] = []

    for idx, seg in enumerate(segments):
        in_idx = clip_to_input_idx[seg.clip_path]
        label = f"v{idx}"
        seek_expr = (
            f"trim=start={seg.seek_point:.3f}:duration={seg.duration:.3f},"
            if seg.seek_point > 0
            else f"trim=duration={seg.duration:.3f},"
        )

        # Dynamic camera motion across cuts to keep visual pacing active (The 2.5s rule)
        motion_style = idx % 3
        dur_safe = max(0.1, seg.duration)
        if motion_style == 0:
            scale_crop = (
                f"scale=w=1.06*{width}:h=1.06*{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}:'(in_w-{width})/2+((in_w-{width})/2)*(t/{dur_safe:.3f}-0.5)':'(in_h-{height})/2',"
            )
        elif motion_style == 1:
            scale_crop = (
                f"scale=w=1.08*{width}:h=1.08*{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}:'(in_w-{width})*(t/{dur_safe:.3f})':'(in_h-{height})/2',"
            )
        else:
            scale_crop = (
                f"scale=w=1.06*{width}:h=1.06*{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}:'(in_w-{width})/2-((in_w-{width})/2)*(t/{dur_safe:.3f}-0.5)':'(in_h-{height})/2',"
            )

        chain = (
            f"[{in_idx}:v]"
            f"{scale_crop}"
            f"fps={fps},"
            f"{seek_expr}"
            f"setpts=PTS-STARTPTS[{label}]"
        )
        filter_parts.append(chain)
        concat_inputs.append(f"[{label}]")

    num_segments = len(segments)
    concat_filter = f"{''.join(concat_inputs)}concat=n={num_segments}:v=1:a=0[v]"
    filter_parts.append(concat_filter)
    video_filtergraph = ";\n".join(filter_parts)

    # ── Build audio filter ─────────────────────────────────────────────
    # Layer an atmospheric low-frequency tension rumble ducked cleanly under speech
    audio_filtergraph = (
        f"aevalsrc='0.025*sin(2*PI*55*t)+0.015*sin(2*PI*110*t+sin(2*PI*0.3*t))+0.01*sin(2*PI*165*t)':"
        f"d={target_render_duration:.3f}:s=44100[bg]; "
        f"[{audio_input_idx}:a]loudnorm=I=-14:LRA=1:TP=-1.5,"
        f"aformat=sample_rates=44100:channel_layouts=stereo[voice]; "
        f"[bg]volume=0.22,lowpass=f=450[bg_low]; "
        f"[voice][bg_low]amix=inputs=2:duration=first:dropout_transition=2[a]"
    )

    # Subtitle burn-in filter
    subtitle_path = ass_path.as_posix().replace(":", "\\:").replace("'", "\\'")
    subtitle_filter = f"[v]subtitles=filename='{subtitle_path}'[vout]"

    full_filtergraph = f"{video_filtergraph}; {audio_filtergraph}; {subtitle_filter}"

    # ── Assemble FFmpeg command ────────────────────────────────────────
    cmd = [
        settings.ffmpeg_binary,
        "-y",
        *input_args,
        *audio_args,
        "-filter_complex",
        full_filtergraph,
        "-map",
        "[vout]",
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
        "-t",
        f"{target_render_duration:.3f}",
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
    await _validate_rendered(output_path, settings, expected_duration=target_render_duration)

    logger.info(
        "Render complete: %s (%.1f MB)",
        output_path,
        output_path.stat().st_size / 1_048_576,
    )
    return output_path


# ── Validation ────────────────────────────────────────────────────────────


async def _validate_rendered(
    path: Path, settings: Settings, expected_duration: float | None = None
) -> None:
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
    if vs.get("codec_name") != "h264":
        raise TransientError(f"Rendered video is not H.264: {vs.get('codec_name', 'unknown')}")
    if vs.get("r_frame_rate") != f"{settings.video_fps}/1":
        raise TransientError(
            f"Rendered video FPS mismatch: got {vs.get('r_frame_rate', 'unknown')}, "
            f"expected {settings.video_fps}/1"
        )
    if audio_streams[0].get("codec_name") != "aac":
        raise TransientError(
            f"Rendered audio is not AAC: {audio_streams[0].get('codec_name', 'unknown')}"
        )

    fmt = data.get("format", {})
    out_duration = float(fmt.get("duration", 0) or 0)
    expected = expected_duration or settings.target_duration_seconds
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
