"""Offline tests for Phase 4 services."""

import asyncio
from pathlib import Path

import pytest

from shorts_pipeline.config import Settings
from shorts_pipeline.services.llm import ScriptSection, ShortsScript
from shorts_pipeline.services.uploader import build_upload_body, script_hash
from shorts_pipeline.state.history import append_history, read_history, recent_topics_and_hashes
from shorts_pipeline.utils.validation import validate_video


def sample_script() -> ShortsScript:
    return ShortsScript(
        hook="Here is a surprising science fact.",
        sections=[
            ScriptSection(
                heading="Fact",
                text="This fact is genuinely interesting.",
                visual_keywords=["science"],
            ),
            ScriptSection(
                heading="Why",
                text="The reason comes down to simple physics.",
                visual_keywords=["physics"],
            ),
        ],
        cta="Follow for more facts.",
        youtube_title="A science fact",
        youtube_description="A short explanation.",
        youtube_tags=["science"],
    )


def test_upload_body_adds_shorts_metadata(tmp_path: Path):
    body = build_upload_body(sample_script(), Settings(project_root=tmp_path))
    assert body["snippet"]["title"].endswith("#Shorts")
    assert "#Shorts" in body["snippet"]["description"]
    assert "#Shorts" in body["snippet"]["tags"]
    assert body["status"]["privacyStatus"] == "private"


def test_history_round_trip_and_recent_values(tmp_path: Path):
    first = append_history(tmp_path, "Topic one", "Title one", "hash-one")
    append_history(tmp_path, "Topic two", "Title two", "hash-two")
    assert first["timestamp"]
    assert len(read_history(tmp_path)) == 2
    assert recent_topics_and_hashes(tmp_path) == (
        ["Topic one", "Topic two"],
        ["hash-one", "hash-two"],
    )


def test_validate_video_accepts_expected_probe(monkeypatch, tmp_path: Path):
    async def fake_probe(path, settings):
        return {
            "streams": [
                {"codec_type": "video", "width": 1080, "height": 1920},
                {"codec_type": "audio"},
            ],
            "format": {"duration": "45.0"},
        }

    monkeypatch.setattr("shorts_pipeline.utils.validation.probe_media", fake_probe)
    path = tmp_path / "video.mp4"
    path.write_bytes(b"mp4")
    result = asyncio.run(validate_video(path, Settings(project_root=tmp_path)))
    assert result["format"]["duration"] == "45.0"


def test_validate_video_rejects_missing_audio(monkeypatch, tmp_path: Path):
    async def fake_probe(path, settings):
        return {
            "streams": [{"codec_type": "video", "width": 1080, "height": 1920}],
            "format": {"duration": 45},
        }

    monkeypatch.setattr("shorts_pipeline.utils.validation.probe_media", fake_probe)
    path = tmp_path / "video.mp4"
    path.write_bytes(b"mp4")
    with pytest.raises(ValueError, match="no audio"):
        asyncio.run(validate_video(path, Settings(project_root=tmp_path)))


def test_script_hash_is_stable():
    assert script_hash(sample_script()) == script_hash(sample_script())


def test_live_upload_uses_mocked_resumable_worker(monkeypatch, tmp_path: Path):
    from shorts_pipeline.services import uploader

    monkeypatch.setattr(uploader, "_upload_once", lambda path, body, settings: "mock-video-id")
    video = tmp_path / "video.mp4"
    video.write_bytes(b"mp4")
    settings = Settings(
        project_root=tmp_path,
        dry_run=False,
        youtube_client_id="client",
        youtube_client_secret="secret",
        youtube_refresh_token="refresh",
    )
    result = asyncio.run(uploader.upload_video(video, sample_script(), settings))
    assert result == "mock-video-id"
