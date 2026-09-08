"""Environment settings and explicit, stage-specific credential preflight checks.

Constructing Settings neither creates directories nor contacts external services.
Relative paths are resolved against the supplied project root, not the caller's cwd.
Never log model_dump() or ValidationError.errors(): those can contain raw inputs.
"""

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
Stage = Literal["script", "tts", "stock", "subtitles", "render", "validate", "upload", "pipeline"]
SafeText = Annotated[str, Field(min_length=1)]


class Settings(BaseSettings):
    """Load uppercase environment names, using safe dry-run/private defaults."""

    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="forbid",
        validate_default=True,
        frozen=True,
        hide_input_in_errors=True,
        str_strip_whitespace=True,
    )

    project_root: Path = Field(default=PROJECT_ROOT, exclude=True)
    gemini_api_key: SecretStr | None = Field(default=None, repr=False)
    gemini_model: str = Field(
        default="gemini-3.1-flash-lite", pattern=r"^gemini-[a-z0-9][a-z0-9.-]*$"
    )
    gemini_max_output_tokens: int = Field(default=4096, ge=1024, le=8192)
    pexels_api_key: SecretStr | None = Field(default=None, repr=False)
    youtube_client_id: SecretStr | None = Field(default=None, repr=False)
    youtube_client_secret: SecretStr | None = Field(default=None, repr=False)
    youtube_refresh_token: SecretStr | None = Field(default=None, repr=False)

    shorts_topic: str = Field(
        default=(
            "Randomly select: Dark Psychology / Scary Stories or Bite-Sized History / Mysteries"
        ),
        min_length=3,
        max_length=300,
    )
    shorts_style: str = Field(
        default=(
            "Cinematic, dark, curiosity-driven; open with a sudden shocking anomaly (0-2s); "
            "short staccato sentences (max 10 words); no intro filler; ending seamlessly "
            "bridges back to the opening hook"
        ),
        min_length=3,
        max_length=500,
    )
    target_duration_seconds: float = Field(default=45.0, ge=40.0, le=50.0)
    min_duration_seconds: float = Field(default=40.0, ge=35.0, le=50.0)
    max_duration_seconds: float = Field(default=50.0, ge=40.0, le=60.0)

    tts_voice: str = Field(
        default="en-US-ChristopherNeural", pattern=r"^[a-z]{2,3}-[A-Za-z-]+Neural$"
    )
    tts_rate: str = Field(default="+12%", pattern=r"^[+-]\d{1,3}%$")
    tts_pitch: str = Field(default="-1Hz", pattern=r"^[+-]\d{1,3}Hz$")
    tts_volume: str = Field(default="+0%", pattern=r"^[+-]\d{1,3}%$")
    tts_timeout_seconds: float = Field(default=180.0, ge=10, le=600)

    youtube_privacy_status: Literal["private", "unlisted", "public"] = "private"
    youtube_category_id: str = Field(default="27", pattern=r"^[1-9]\d?$")
    youtube_made_for_kids: bool = False
    youtube_contains_synthetic_media: bool = True
    dry_run: bool = True
    dry_run_update_history: bool = False
    publication_channel: str = Field(
        default="configured-youtube-channel", min_length=1, max_length=200
    )
    publication_slot: str = Field(default="manual", min_length=1, max_length=120)
    youtube_verify_timeout_seconds: float = Field(default=120, ge=10, le=600)

    retry_max_attempts: int = Field(default=3, ge=1, le=5)
    retry_base_seconds: float = Field(default=2.0, ge=0.1, le=30)
    retry_max_seconds: float = Field(default=30.0, ge=1, le=120)
    http_timeout_seconds: float = Field(default=30.0, ge=1, le=120)
    download_timeout_seconds: float = Field(default=120.0, ge=5, le=600)
    max_asset_bytes: int = Field(default=80_000_000, ge=1_000_000, le=200_000_000)
    min_asset_bytes: int = Field(default=1024, ge=512, le=1_000_000)
    pexels_results_per_search: int = Field(default=5, ge=1, le=10)
    stock_max_searches_per_section: int = Field(default=4, ge=1, le=6)
    stock_max_downloads_per_section: int = Field(default=3, ge=1, le=5)

    visual_backend: Literal["sketch", "stock"] = "sketch"
    sketch_style_prompt: str = Field(
        default=(
            "Dark historical pencil sketch, vintage charcoal illustration, dramatic chiaroscuro "
            "lighting, detailed line art, atmospheric, 9:16 vertical composition"
        ),
        min_length=3,
        max_length=500,
    )

    ffmpeg_binary: SafeText = "ffmpeg"
    ffprobe_binary: SafeText = "ffprobe"
    ffmpeg_timeout_seconds: float = Field(default=1200, ge=30, le=3600)
    ffprobe_timeout_seconds: float = Field(default=30, ge=1, le=120)
    video_width: Literal[1080] = 1080
    video_height: Literal[1920] = 1920
    video_fps: Literal[30] = 30
    video_crf: int = Field(default=21, ge=16, le=28)
    video_preset: Literal["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"] = (
        "veryfast"
    )
    ffmpeg_threads: int = Field(default=2, ge=1, le=16)
    audio_bitrate_kbps: Literal[128, 160, 192] = 192

    caption_font: str = Field(default="DejaVu Sans", min_length=1, max_length=80)
    caption_font_size: int = Field(default=82, ge=40, le=120)
    caption_words_per_unit: int = Field(default=2, ge=1, le=6)
    caption_max_chars_per_line: int = Field(default=24, ge=12, le=36)
    caption_margin_x: int = Field(default=100, ge=60, le=200)
    caption_margin_bottom: int = Field(default=380, ge=250, le=700)
    caption_outline: int = Field(default=6, ge=2, le=10)
    caption_primary_color: str = Field(default="&H00FFFFFF", pattern=r"^&H[0-9A-Fa-f]{8}$")
    caption_highlight_color: str = Field(default="&H0000D7FF", pattern=r"^&H[0-9A-Fa-f]{8}$")

    output_dir: Path = Path("output")
    work_dir: Path = Path("work")
    state_dir: Path = Path("state")
    fallback_dir: Path = Path("assets/fallback")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    history_backend: Literal["local", "github"] = "local"
    history_recent_limit: int = Field(default=60, ge=10, le=200)
    history_similarity_threshold: float = Field(default=0.72, ge=0.3, le=0.95)
    github_repository: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"
    )
    github_token: SecretStr | None = Field(default=None, repr=False)
    history_branch: str = Field(default="shorts-state", pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

    @field_validator(
        "video_width", "video_height", "video_fps", "audio_bitrate_kbps", mode="before"
    )
    @classmethod
    def parse_integer_choices(cls, value: object) -> object:
        # Literal[int] does not coerce dotenv strings, unlike ordinary int fields.
        if isinstance(value, str) and value.isascii() and value.isdigit():
            return int(value)
        return value

    @field_validator(
        "dry_run",
        "dry_run_update_history",
        "youtube_made_for_kids",
        "youtube_contains_synthetic_media",
        mode="before",
    )
    @classmethod
    def parse_boolean(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
            raise ValueError("boolean settings must be true or false")
        return value

    @field_validator(
        "gemini_api_key",
        "pexels_api_key",
        "youtube_client_id",
        "youtube_client_secret",
        "youtube_refresh_token",
        "github_token",
        mode="before",
    )
    @classmethod
    def normalize_secret(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("tts_rate", "tts_volume", "tts_pitch")
    @classmethod
    def validate_prosody(cls, value: str, info: ValidationInfo) -> str:
        amount = int(value.removesuffix("%").removesuffix("Hz"))
        lower, upper = (-100, 100) if info.field_name == "tts_pitch" else (-50, 100)
        if not lower <= amount <= upper:
            raise ValueError(f"{info.field_name} is outside the supported safety range")
        return value

    @field_validator("caption_font")
    @classmethod
    def validate_font(cls, value: str) -> str:
        if any(char in value for char in ",\r\n{}\\") or any(ord(char) < 32 for char in value):
            raise ValueError("caption_font must be an ASS-safe font family name")
        return value

    @field_validator("ffmpeg_binary", "ffprobe_binary")
    @classmethod
    def validate_binary(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("binary must be an executable name or path, not control characters")
        return value

    @model_validator(mode="after")
    def validate_relationships(self) -> Self:
        if (
            not self.min_duration_seconds
            <= self.target_duration_seconds
            <= self.max_duration_seconds
        ):
            raise ValueError("target duration must fall between min and max duration")
        if self.min_duration_seconds >= self.max_duration_seconds:
            raise ValueError("min duration must be less than max duration")
        if self.retry_base_seconds > self.retry_max_seconds:
            raise ValueError("retry_base_seconds must not exceed retry_max_seconds")
        if self.min_asset_bytes >= self.max_asset_bytes:
            raise ValueError("min_asset_bytes must be less than max_asset_bytes")

        root = self.project_root.expanduser().resolve()
        object.__setattr__(self, "project_root", root)
        for name in ("output_dir", "work_dir", "state_dir", "fallback_dir"):
            path = getattr(self, name).expanduser()
            resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
            if not resolved.is_relative_to(root) or resolved == root:
                raise ValueError(f"{name} must be a subdirectory inside project_root")
            object.__setattr__(self, name, resolved)

        # Protect source, credentials and persisted history from future work-dir cleanup.
        writable = (self.output_dir, self.work_dir, self.state_dir)
        protected = tuple(
            root / name for name in ("src", "tests", "scripts", ".github", ".venv", ".git", "docs")
        )
        for path in writable:
            for other in (*protected, self.fallback_dir):
                if path.is_relative_to(other) or other.is_relative_to(path):
                    raise ValueError(
                        "writable directories must not overlap source or fallback assets"
                    )
        for index, path in enumerate(writable):
            for other in writable[index + 1 :]:
                if path.is_relative_to(other) or other.is_relative_to(path):
                    raise ValueError("output, work, and state directories must not overlap")
        return self

    def require_for(self, stage: Stage) -> None:
        """Fail early without printing credential values; stock can run without a key."""
        allowed = {
            "script",
            "tts",
            "stock",
            "subtitles",
            "render",
            "validate",
            "upload",
            "pipeline",
        }
        if stage not in allowed:
            raise ValueError("Unknown pipeline stage")
        required: list[str] = []
        if stage in {"script", "pipeline"}:
            required.append("gemini_api_key")
        if stage == "upload" and self.dry_run:
            raise ValueError("Upload is disabled while DRY_RUN=true")
        if stage == "upload" or (stage == "pipeline" and not self.dry_run):
            required.extend(("youtube_client_id", "youtube_client_secret", "youtube_refresh_token"))
        if self.history_backend == "github" and stage in {"script", "pipeline", "upload"}:
            required.extend(("github_repository", "github_token"))
        missing = []
        for name in required:
            value = getattr(self, name)
            raw = value.get_secret_value() if isinstance(value, SecretStr) else value
            if not raw or str(raw).lower().startswith(("replace_", "your_", "<")):
                missing.append(name.upper())
        if missing:
            raise ValueError("Missing required configuration: " + ", ".join(missing))


def load_settings(project_root: Path | None = None, env_file: Path | None = None) -> Settings:
    """Read root/.env explicitly; process environment overrides dotenv values.

    No directories are created, and credentials are checked only via require_for().
    An explicit relative env_file is resolved under project_root.
    """
    root = (project_root or PROJECT_ROOT).expanduser().resolve()
    dotenv = root / (env_file or Path(".env"))
    return Settings(project_root=root, _env_file=dotenv)
