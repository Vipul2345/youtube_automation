"""Command-line orchestration for the complete Shorts pipeline."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import uuid
from pathlib import Path

from shorts_pipeline.config import Settings, load_settings
from shorts_pipeline.services.editorial import validate_script
from shorts_pipeline.services.llm import generate_script
from shorts_pipeline.services.renderer import RenderSegment, render_video
from shorts_pipeline.services.sketch import resolve_sketch_assets_for_sections
from shorts_pipeline.services.stock import resolve_assets_for_section
from shorts_pipeline.services.subtitles import write_ass_file
from shorts_pipeline.services.tts import synthesize_to_files
from shorts_pipeline.services.uploader import script_hash, upload_video
from shorts_pipeline.state.history import (
    append_history,
    is_duplicate_story,
    recent_story_titles,
    recent_topics_and_hashes,
)
from shorts_pipeline.state.ledger import (
    new_intent,
    record,
    stable_publication_id,
    write_receipt,
)
from shorts_pipeline.utils.logging import configure_logging
from shorts_pipeline.utils.validation import validate_video

logger = logging.getLogger(__name__)

TOPIC_CATEGORIES = (
    "Dark Psychology / Scary Stories",
    "Bite-Sized History / Mysteries",
)


async def run_pipeline(settings: Settings) -> Path:
    """Generate, render, validate, upload, and record one Short."""
    settings.require_for("pipeline")
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.state_dir.mkdir(parents=True, exist_ok=True)

    recent_topics, _ = recent_topics_and_hashes(settings.state_dir, settings.history_recent_limit)
    recent_titles = recent_story_titles(settings.state_dir, settings.history_recent_limit)
    api_key = settings.gemini_api_key
    assert api_key is not None
    selected_topic = random.choice(TOPIC_CATEGORIES)
    execution_id = os.getenv("GITHUB_RUN_ID") or str(uuid.uuid4())
    slot = os.getenv("PUBLICATION_SLOT", settings.publication_slot)
    publication_id = stable_publication_id(settings.publication_channel, slot)
    recent_topics = [*recent_topics, *recent_titles]
    script = None
    for attempt in range(1, settings.retry_max_attempts + 1):
        script = await generate_script(
            api_key.get_secret_value(),
            model=settings.gemini_model,
            topic=selected_topic,
            style=settings.shorts_style,
            target_duration=settings.target_duration_seconds,
            recent_topics=recent_topics,
            max_retries=settings.retry_max_attempts,
            http_timeout=settings.http_timeout_seconds,
            max_output_tokens=settings.gemini_max_output_tokens,
        )
        if not is_duplicate_story(
            script.youtube_title,
            script_hash(script),
            settings.state_dir,
            settings.history_similarity_threshold,
            settings.history_recent_limit,
            script.full_script(),
        ):
            break
        logger.warning(
            "Generated story duplicates recent history; regenerating (%d/%d)",
            attempt,
            settings.retry_max_attempts,
        )
        recent_topics.append(script.youtube_title)
    else:
        raise RuntimeError("Unable to generate a story that is new relative to recent history")
    assert script is not None
    validate_script(script, settings, selected_topic)
    intent = None
    if not settings.dry_run:
        intent = new_intent(settings.state_dir, publication_id, execution_id, script_hash(script))
        intent = record(
            settings.state_dir,
            intent,
            "scripted",
            title=script.youtube_title,
            requested_visibility=settings.youtube_privacy_status,
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
    if settings.visual_backend == "sketch":
        clips = await resolve_sketch_assets_for_sections(
            script.sections, settings, settings.work_dir
        )
    else:
        for index, section in enumerate(script.sections):
            clips.extend(
                await resolve_assets_for_section(
                    section.visual_keywords, index, settings, settings.work_dir
                )
            )
    if not clips:
        raise RuntimeError("No visual clips were produced")

    # The configured target is authoritative.  TTS can run longer than the
    # requested duration (for example when the generated script is verbose),
    # but allowing that value to drive the render can create an upload-invalid
    # video longer than YouTube Shorts' 60-second limit.
    total_duration = settings.target_duration_seconds
    # Give the opening visual a quick 4-second beat, then let the explanatory
    # visuals breathe evenly. This creates an immediate pattern interrupt while
    # preserving the configured total duration.
    opening_duration = min(4.0, total_duration * 0.12)
    if len(clips) == 1:
        durations = [total_duration]
    else:
        body_duration = (total_duration - opening_duration) / (len(clips) - 1)
        durations = [opening_duration] + [body_duration] * (len(clips) - 1)
    segments = [RenderSegment(clip.file_path, durations[index]) for index, clip in enumerate(clips)]
    await render_video(output_path, audio_path, ass_path, segments, settings)
    if intent is not None:
        intent = record(settings.state_dir, intent, "rendered", output_path=str(output_path))
    await validate_video(output_path, settings)
    if intent is not None:
        intent = record(settings.state_dir, intent, "validated")
    if settings.dry_run:
        youtube_video_id = await upload_video(output_path, script, settings)
    else:
        intent = record(settings.state_dir, intent, "uploading")
        try:
            youtube_video_id = await upload_video(output_path, script, settings)
        except TimeoutError as exc:
            record(
                settings.state_dir, intent, "upload_outcome_unknown", error_type=type(exc).__name__
            )
            raise RuntimeError("Upload outcome is unknown; do not retry blindly") from exc
        except Exception as exc:
            record(settings.state_dir, intent, "failed", error_type=type(exc).__name__)
            raise
        intent = record(settings.state_dir, intent, "uploaded", youtube_video_id=youtube_video_id)
        write_receipt(settings.state_dir, intent)
        intent = record(settings.state_dir, intent, "published")

    if not settings.dry_run or settings.dry_run_update_history:
        append_history(
            settings.state_dir,
            selected_topic,
            script.youtube_title,
            script_hash(script),
            settings.history_recent_limit,
            script.full_script(),
            youtube_video_id or "",
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
