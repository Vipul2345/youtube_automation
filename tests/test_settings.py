"""Offline configuration tests: no production credentials or service calls."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from shorts_pipeline.config import Settings, load_settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
        monkeypatch.delenv(name.lower(), raising=False)


def test_safe_defaults_and_no_io(tmp_path):
    root = tmp_path / "not-created"
    settings = Settings(project_root=root)
    assert settings.dry_run is True
    assert settings.dry_run_update_history is False
    assert settings.youtube_privacy_status == "private"
    assert settings.gemini_model == "gemini-3.1-flash-lite"
    assert settings.target_duration_seconds == 45
    assert (settings.video_width, settings.video_height, settings.video_fps) == (1080, 1920, 30)
    assert settings.work_dir == root / "work"
    assert not root.exists()


def test_env_example_loads_and_covers_all_public_settings():
    root = Path(__file__).resolve().parents[1]
    settings = load_settings(root, Path(".env.example"))
    assert settings.gemini_api_key is None
    assert settings.dry_run is True
    names = {
        line.split("=", 1)[0].lower()
        for line in (root / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    assert names == set(Settings.model_fields) - {"project_root"}


def test_environment_overrides_dotenv_and_cwd(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("DRY_RUN=true\nTTS_RATE=+5%\n", encoding="utf-8")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TTS_RATE", "")
    monkeypatch.chdir(tmp_path.parent)
    settings = load_settings(tmp_path)
    assert settings.dry_run is False
    assert settings.tts_rate == "+5%"
    assert settings.output_dir == tmp_path / "output"


@pytest.mark.parametrize(
    ("value", "expected"), [("false", False), ("true", True), ("0", False), ("1", True)]
)
def test_boolean_environment_values_are_parsed_explicitly(tmp_path, value, expected):
    settings = Settings(project_root=tmp_path, dry_run=value)
    assert settings.dry_run is expected


def test_invalid_boolean_environment_value_is_rejected(tmp_path):
    with pytest.raises(ValidationError):
        Settings(project_root=tmp_path, dry_run="not-a-boolean")


@pytest.mark.parametrize(
    "values",
    [
        {"youtube_privacy_status": "friends"},
        {"dry_run": "maybe"},
        {"target_duration_seconds": 70},
        {"target_duration_seconds": 45, "min_duration_seconds": 46},
        {"min_duration_seconds": 45, "max_duration_seconds": 45},
        {"retry_max_attempts": 0},
        {"retry_max_attempts": 100},
        {"retry_base_seconds": 20, "retry_max_seconds": 10},
        {"max_asset_bytes": 1_000_000, "min_asset_bytes": 1_000_000},
        {"tts_rate": "fast"},
        {"tts_rate": "-100%"},
        {"tts_pitch": "+101Hz"},
        {"tts_volume": "-51%"},
        {"tts_voice": "voice; malicious"},
        {"caption_font": "Font,Injected"},
        {"caption_font": "Font\nInjected"},
        {"caption_primary_color": "white"},
        {"video_width": 720},
        {"video_fps": 60},
        {"gemini_model": "../../model"},
        {"history_branch": "../../main"},
        {"github_repository": "https://github.com/owner/repo"},
        {"work_dir": "../outside"},
        {"work_dir": "."},
        {"work_dir": "state/tmp"},
        {"work_dir": "assets"},
        {"work_dir": "src/tmp"},
        {"work_dir": ".git"},
        {"work_dir": "docs"},
        {"output_dir": "work"},
    ],
)
def test_invalid_settings_rejected(tmp_path, values):
    with pytest.raises(ValidationError):
        Settings(project_root=tmp_path, **values)


def test_unknown_dotenv_key_rejected_without_input_leak(tmp_path):
    (tmp_path / ".env").write_text("GEMINI_APY_KEY=sensitive-test-value\n", encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        load_settings(tmp_path)
    assert "sensitive-test-value" not in str(exc.value)


def test_secret_representation_and_preflight_errors_are_redacted(tmp_path):
    secret = "sensitive-test-value"
    settings = Settings(project_root=tmp_path, gemini_api_key=secret)
    assert secret not in repr(settings)
    assert secret not in settings.model_dump_json()
    settings.require_for("script")
    with pytest.raises(ValueError, match="DRY_RUN") as exc:
        settings.require_for("upload")
    assert secret not in str(exc.value)


def test_stage_specific_credentials(tmp_path):
    settings = Settings(project_root=tmp_path)
    for stage in ("tts", "stock", "subtitles", "render", "validate"):
        settings.require_for(stage)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        settings.require_for("pipeline")
    live = Settings(project_root=tmp_path, dry_run=False, gemini_api_key="test-key")
    with pytest.raises(ValueError, match="YOUTUBE_REFRESH_TOKEN"):
        live.require_for("pipeline")
    configured = Settings(
        project_root=tmp_path,
        dry_run=False,
        gemini_api_key="test-key",
        youtube_client_id="test-client",
        youtube_client_secret="test-secret",
        youtube_refresh_token="test-refresh",
    )
    configured.require_for("pipeline")
    configured.require_for("upload")


@pytest.mark.parametrize("key", ["", "   ", "replace_with_key", "your_api_key", "<key>"])
def test_empty_and_example_credentials_fail_preflight(tmp_path, key):
    settings = Settings(project_root=tmp_path, gemini_api_key=key)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        settings.require_for("script")


def test_github_history_requires_ephemeral_token_and_repository(tmp_path):
    settings = Settings(project_root=tmp_path, history_backend="github", gemini_api_key="test-key")
    with pytest.raises(ValueError, match="GITHUB_REPOSITORY, GITHUB_TOKEN"):
        settings.require_for("script")
    configured = Settings(
        project_root=tmp_path,
        history_backend="github",
        gemini_api_key="test-key",
        github_repository="owner/repo",
        github_token="test-token",
    )
    configured.require_for("pipeline")


def test_unknown_stage_is_not_silently_accepted(tmp_path):
    with pytest.raises(ValueError, match="Unknown pipeline stage"):
        Settings(project_root=tmp_path).require_for("invalid")
