"""Command-line orchestration for the complete Shorts pipeline."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from shorts_pipeline.config import Settings, load_settings
from shorts_pipeline.services.llm import generate_script
from shorts_pipeline.services.renderer import RenderSegment, render_video
from shorts_pipeline.services.stock import resolve_assets_for_section
from shorts_pipeline.services.subtitles import write_ass_file
from shorts_pipeline.services.tts import synthesize_to_files
from shorts_pipeline.services.uploader import script_hash, upload_video
from shorts_pipeline.state.history import append_history, recent_topics_and_hashes
from shorts_pipeline.utils.logging import configure_logging
from shorts_pipeline.utils.validation import validate_video

logger = logging.getLogger(__name__)


async def run_pipeline(settings: Settings) -> Path:
    """Generate, render, validate, upload, and record one Short."""
    settings.require_for("pipeline")
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.state_dir.mkdir(parents=True, exist_ok=True)

    recent_topics, _ = recent_topics_and_hashes(settings.state_dir, settings.history_recent_limit)
    api_key = settings.gemini_api_key
    assert api_key is not None
    script = await generate_script(
        api_key.get_secret_value(),
        model=settings.gemini_model,
        topic=settings.shorts_topic,
        style=settings.shorts_style,
        target_duration=settings.target_duration_seconds,
        recent_topics=recent_topics,
        max_retries=settings.retry_max_attempts,
        http_timeout=settings.http_timeout_seconds,
        max_output_tokens=settings.gemini_max_output_tokens,
    )

    stem = "short"
    audio_path = settings.work_dir / f"{stem}.mp3"
    metadata_path = settings.work_dir / f"{stem}_tts.json"
    ass_path = settings.work_dir / f"{stem}.ass"
    output_path = settings.output_dir / f"{stem}.mp4"
    tts_result = await synthesize_to_files(
        script.full_script(), settings, audio_path, metadata_path
    )
    await write_ass_file(tts_result.word_boundaries, ass_path, settings)

    clips = []
    for index, section in enumerate(script.sections):
        clips.extend(
            await resolve_assets_for_section(
                section.visual_keywords, index, settings, settings.work_dir
            )
        )
    if not clips:
        raise RuntimeError("No visual clips were produced")

    total_duration = tts_result.duration_seconds or settings.target_duration_seconds
    segment_duration = total_duration / len(clips)
    segments = [RenderSegment(clip.file_path, segment_duration) for clip in clips]
    await render_video(output_path, audio_path, ass_path, segments, settings)
    await validate_video(output_path, settings)
    await upload_video(output_path, script, settings)

    if not settings.dry_run or settings.dry_run_update_history:
        append_history(
            settings.state_dir,
            settings.shorts_topic,
            script.youtube_title,
            script_hash(script),
            settings.history_recent_limit,
        )
    logger.info("Pipeline complete: %s", output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and upload a YouTube Short")
    parser.add_argument("--project-root", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings(args.project_root)
    configure_logging(settings.log_level)
    asyncio.run(run_pipeline(settings))


if __name__ == "__main__":
    main()
