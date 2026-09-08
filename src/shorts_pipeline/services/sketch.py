"""Sketch image generation and Ken Burns motion animation service."""

from __future__ import annotations

import asyncio
import base64
import logging
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import httpx

from shorts_pipeline.config.settings import Settings
from shorts_pipeline.services.stock import StockClip
from shorts_pipeline.utils.retry import TransientError

if TYPE_CHECKING:
    from shorts_pipeline.services.llm import ScriptSection

logger = logging.getLogger(__name__)

IMAGEN_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def build_sketch_prompt(section_text: str, visual_keywords: list[str], style_prompt: str) -> str:
    """Build a detailed image generation prompt for a sketch illustration."""
    keywords_str = ", ".join(visual_keywords)
    return (
        f"{style_prompt}. "
        f"Subject/Scene: {section_text}. "
        f"Visual details: {keywords_str}. "
        "High contrast pencil and ink drawing, dramatic atmosphere, 9:16 vertical composition."
    )


async def generate_sketch_image(
    prompt: str,
    dest_path: Path,
    settings: Settings,
) -> Path:
    """Generate a sketch image using Imagen 3 REST API or programmatic fallback."""
    api_key = settings.gemini_api_key
    api_key_value = api_key.get_secret_value() if api_key else None

    if api_key_value:
        url = f"{IMAGEN_API_BASE}/models/imagen-3.0-generate-002:generateImages?key={api_key_value}"
        body = {
            "prompt": prompt,
            "config": {
                "numberOfImages": 1,
                "outputMimeType": "image/jpeg",
                "aspectRatio": "9:16",
            },
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.http_timeout_seconds)
            ) as client:
                response = await client.post(
                    url,
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code == 200:
                    data = response.json()
                    images = data.get("generatedImages", [])
                    if images:
                        b64_data = images[0].get("image", {}).get("imageBytes")
                        if b64_data:
                            img_bytes = base64.b64decode(b64_data)
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            dest_path.write_bytes(img_bytes)
                            logger.info("Generated AI sketch image: %s", dest_path.name)
                            return dest_path
                else:
                    logger.warning(
                        "Imagen API returned HTTP %d: %s",
                        response.status_code,
                        response.text[:200],
                    )
        except Exception as exc:
            logger.warning("Imagen API call failed (%s), using sketch fallback", exc)

    return await generate_fallback_sketch_image(dest_path, settings)


async def generate_fallback_sketch_image(dest_path: Path, settings: Settings) -> Path:
    """Generate a programmatic dark charcoal sketch backdrop image using FFmpeg."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    width = settings.video_width
    height = settings.video_height

    cmd = [
        settings.ffmpeg_binary,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=0x181824:s={width}x{height}:d=1",
        "-vf",
        "noise=alls=20:allf=t+u,vignette=PI/4,format=yuv420p",
        "-vframes",
        "1",
        str(dest_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")[:500]
        raise TransientError(f"Fallback sketch image generation failed: {stderr_text}")

    logger.info("Generated fallback sketch image: %s", dest_path.name)
    return dest_path


async def animate_sketch_to_clip(
    image_path: Path,
    output_clip_path: Path,
    duration: float,
    animation_type: Literal["zoom_in", "zoom_out", "pan_right", "pan_left"],
    settings: Settings,
) -> Path:
    """Animate a static sketch image using FFmpeg zoompan (Ken Burns effect)."""
    output_clip_path.parent.mkdir(parents=True, exist_ok=True)
    width = settings.video_width
    height = settings.video_height
    fps = settings.video_fps
    num_frames = int(duration * fps)

    if animation_type == "zoom_in":
        zoom_expr = (
            f"zoompan=z='min(zoom+0.0015,1.25)':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={num_frames}:s={width}x{height}:fps={fps}"
        )
    elif animation_type == "zoom_out":
        zoom_expr = (
            f"zoompan=z='max(1.25-0.0015*on,1.0)':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={num_frames}:s={width}x{height}:fps={fps}"
        )
    elif animation_type == "pan_right":
        zoom_expr = (
            f"zoompan=z=1.15:x='if(eq(on,1),0,min(x+1,iw-iw/zoom))':"
            f"y='ih/2-(ih/zoom/2)':d={num_frames}:s={width}x{height}:fps={fps}"
        )
    else:  # pan_left
        zoom_expr = (
            f"zoompan=z=1.15:x='if(eq(on,1),iw-iw/zoom,max(x-1,0))':"
            f"y='ih/2-(ih/zoom/2)':d={num_frames}:s={width}x{height}:fps={fps}"
        )

    cmd = [
        settings.ffmpeg_binary,
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-vf",
        f"{zoom_expr},format=yuv420p",
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        settings.video_preset,
        "-crf",
        str(settings.video_crf),
        "-r",
        str(fps),
        "-an",
        str(output_clip_path),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")[:500]
        raise TransientError(f"Sketch animation failed: {stderr_text}")

    logger.info(
        "Animated sketch clip created: %s (%.1fs, %s)",
        output_clip_path.name,
        duration,
        animation_type,
    )
    return output_clip_path


async def resolve_sketch_assets_for_sections(
    sections: list[ScriptSection],
    settings: Settings,
    work_dir: Path,
) -> list[StockClip]:
    """Generate sketch images for each section and convert them into animated MP4 clips."""
    clips: list[StockClip] = []
    animation_types: list[Literal["zoom_in", "zoom_out", "pan_right", "pan_left"]] = [
        "zoom_in",
        "pan_right",
        "zoom_out",
        "pan_left",
    ]

    section_duration = settings.target_duration_seconds / max(1, len(sections))

    for index, section in enumerate(sections):
        safe_key = secrets.token_hex(4)
        image_path = work_dir / f"sketch_s{index}_{safe_key}.jpg"
        clip_path = work_dir / f"animated_sketch_s{index}_{safe_key}.mp4"

        prompt = build_sketch_prompt(
            section.text, section.visual_keywords, settings.sketch_style_prompt
        )

        await generate_sketch_image(prompt, image_path, settings)

        anim_type = animation_types[index % len(animation_types)]

        await animate_sketch_to_clip(
            image_path, clip_path, section_duration, anim_type, settings
        )

        clips.append(
            StockClip(
                file_path=clip_path,
                source_url="generated://sketch-illustration",
                attribution="AI Sketch Illustration + Ken Burns Motion",
                license_note="Generated by Pipeline",
                duration_seconds=section_duration,
                width=settings.video_width,
                height=settings.video_height,
                is_fallback=False,
            )
        )

    return clips
