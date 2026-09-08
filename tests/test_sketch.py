"""Offline unit tests for sketch image generation and Ken Burns animation service."""

import asyncio
from pathlib import Path

from shorts_pipeline.config import Settings
from shorts_pipeline.services.llm import ScriptSection
from shorts_pipeline.services.sketch import (
    animate_sketch_to_clip,
    build_sketch_prompt,
    generate_fallback_sketch_image,
    resolve_sketch_assets_for_sections,
)
from shorts_pipeline.services.stock import probe_clip


def test_build_sketch_prompt():
    prompt = build_sketch_prompt(
        section_text="An ancient temple stood hidden deep in the jungle.",
        visual_keywords=["ancient temple", "jungle"],
        style_prompt="Dark historical pencil sketch",
    )
    assert "Dark historical pencil sketch" in prompt
    assert "An ancient temple stood hidden" in prompt
    assert "ancient temple, jungle" in prompt


def test_generate_fallback_sketch_image(tmp_path: Path):
    dest = tmp_path / "test_sketch.jpg"
    settings = Settings(project_root=tmp_path)
    result = asyncio.run(generate_fallback_sketch_image(dest, settings))
    assert result.is_file()
    assert result.stat().st_size > 0


def test_animate_sketch_to_clip(tmp_path: Path):
    settings = Settings(project_root=tmp_path)
    img_path = tmp_path / "test_sketch.jpg"
    asyncio.run(generate_fallback_sketch_image(img_path, settings))

    clip_path = tmp_path / "test_clip.mp4"
    asyncio.run(
        animate_sketch_to_clip(
            image_path=img_path,
            output_clip_path=clip_path,
            duration=3.0,
            animation_type="zoom_in",
            settings=settings,
        )
    )
    assert clip_path.is_file()
    duration, width, height = asyncio.run(probe_clip(clip_path, settings.ffprobe_binary))
    assert width == settings.video_width
    assert height == settings.video_height
    assert abs(duration - 3.0) < 0.5


def test_resolve_sketch_assets_for_sections(tmp_path: Path):
    settings = Settings(project_root=tmp_path)
    sections = [
        ScriptSection(
            heading="Intro",
            text="The expedition ventured into uncharted territory.",
            visual_keywords=["expedition", "map"],
        ),
        ScriptSection(
            heading="Climax",
            text="They uncovered a glowing relic beneath the floorboards.",
            visual_keywords=["relic", "glowing"],
        ),
    ]
    clips = asyncio.run(resolve_sketch_assets_for_sections(sections, settings, tmp_path))
    assert len(clips) == 2
    assert all(c.file_path.is_file() for c in clips)
    assert clips[0].attribution == "AI Sketch Illustration + Ken Burns Motion"
