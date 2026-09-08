"""Script to render a sample 1080x1920 YouTube Short MP4 locally using Edge-TTS."""

import asyncio
import logging
from pathlib import Path

from shorts_pipeline.config import Settings
from shorts_pipeline.services.editorial import validate_script
from shorts_pipeline.services.llm import ScriptSection, ShortsScript
from shorts_pipeline.services.renderer import RenderSegment, render_video
from shorts_pipeline.services.stock import generate_fallback_clip
from shorts_pipeline.services.subtitles import write_ass_file
from shorts_pipeline.services.tts import synthesize_to_files
from shorts_pipeline.utils.logging import configure_logging
from shorts_pipeline.utils.validation import validate_video

logger = logging.getLogger(__name__)


def create_sample_script() -> ShortsScript:
    return ShortsScript(
        hook="The sunlight on your face is already eight minutes old.",
        sections=[
            ScriptSection(
                heading="Fact 1",
                text=(
                    "When you look at the bright Sun in the sky, you are seeing it "
                    "as it was 8 minutes ago in the distant past."
                ),
                visual_keywords=["sun", "space"],
            ),
            ScriptSection(
                heading="Fact 2",
                text=(
                    "If the Sun vanished right now, Earth would stay bathed in sunlight "
                    "for another 500 seconds before darkness falls."
                ),
                visual_keywords=["stars", "cosmos"],
            ),
            ScriptSection(
                heading="Fact 3",
                text=(
                    "Photons created in the Sun's core take 100,000 years to reach the surface, "
                    "but only 8 minutes to reach Earth."
                ),
                visual_keywords=["photons", "galaxy"],
            ),
        ],
        cta="Follow for more mind-bending space and science facts every single day!",
        youtube_title="The 8-Minute Sun Mystery #Shorts",
        youtube_description="Mindblowing space and science facts about light travel time. #Shorts",
        youtube_tags=["science", "space", "facts", "shorts"],
    )


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    settings = Settings(project_root=root, dry_run=True)
    configure_logging("INFO")

    logger.info("Starting local sample video rendering...")
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    script = create_sample_script()
    validate_script(script, settings, "Bite-Sized History / Mysteries")

    stem = "sample_short"
    audio_path = settings.work_dir / f"{stem}.mp3"
    metadata_path = settings.work_dir / f"{stem}_tts.json"
    ass_path = settings.work_dir / f"{stem}.ass"
    output_path = settings.output_dir / f"{stem}.mp4"

    logger.info("1/4 Synthesizing voice narration with Edge-TTS...")
    tts_result = await synthesize_to_files(
        script.full_script(), settings, audio_path, metadata_path
    )

    logger.info("2/4 Generating ASS subtitle captions...")
    await write_ass_file(tts_result.word_boundaries, ass_path, settings)

    logger.info("3/4 Generating visual clips...")
    segments = []
    seg_dur = max(5.0, tts_result.duration_seconds / len(script.sections))
    for idx in range(len(script.sections)):
        clip_file = settings.work_dir / f"{stem}_clip{idx + 1}.mp4"
        await generate_fallback_clip(
            clip_file,
            duration=seg_dur,
            width=settings.video_width,
            height=settings.video_height,
            fps=settings.video_fps,
        )
        segments.append(RenderSegment(clip_file, seg_dur))

    logger.info("4/4 Rendering 1080x1920 MP4 video with FFmpeg...")
    await render_video(output_path, audio_path, ass_path, segments, settings)

    logger.info("Validating rendered MP4 with ffprobe...")
    probe_res = await validate_video(output_path, settings)

    logger.info("SUCCESS! Rendered video saved to: %s", output_path)
    logger.info(
        "Video Specs: Duration: %s seconds, Size: %.2f MB",
        probe_res["format"]["duration"],
        output_path.stat().st_size / 1_048_576,
    )


if __name__ == "__main__":
    asyncio.run(main())
