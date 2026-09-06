"""YouTube Data API v3 upload service."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaFileUpload

from shorts_pipeline.config.settings import Settings
from shorts_pipeline.services.llm import ShortsScript
from shorts_pipeline.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CHUNK_SIZE = 4 * 1024 * 1024


def _credentials(settings: Settings) -> Credentials:
    """Create OAuth credentials from the configured refresh token."""
    values = [
        settings.youtube_client_id,
        settings.youtube_client_secret,
        settings.youtube_refresh_token,
    ]
    client_id, client_secret, refresh_token = [
        value.get_secret_value() if value else "" for value in values
    ]
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    if not credentials.valid:
        credentials.refresh(GoogleAuthRequest())
    return credentials


def _service(settings: Settings) -> Resource:
    return build("youtube", "v3", credentials=_credentials(settings), cache_discovery=False)


def build_upload_body(script: ShortsScript, settings: Settings) -> dict:
    """Build YouTube metadata, ensuring the Shorts marker is present everywhere."""
    description = script.youtube_description
    if "#shorts" not in description.lower():
        description = f"{description.rstrip()}\n\n#Shorts"
    tags = list(script.youtube_tags)
    if not any(tag.lower().lstrip("#") == "shorts" for tag in tags):
        tags.append("#Shorts")
    title = f"{script.youtube_title.rstrip()} #Shorts"
    if len(title) > 100:
        title = f"{script.youtube_title.rstrip()[:91].rstrip()} #Shorts"
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": settings.youtube_category_id,
        },
        "status": {
            "privacyStatus": settings.youtube_privacy_status,
            "selfDeclaredMadeForKids": settings.youtube_made_for_kids,
        },
    }


def _upload_once(path: Path, body: dict, settings: Settings) -> str:
    service = _service(settings)
    request = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(path), chunksize=CHUNK_SIZE, resumable=True),
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("Upload progress: %.1f%%", status.progress() * 100)
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube upload response did not contain a video ID")
    return video_id


async def upload_video(video_path: Path, script: ShortsScript, settings: Settings) -> str | None:
    """Upload a final MP4, or log metadata without calling YouTube in dry-run mode."""
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    body = build_upload_body(script, settings)
    if settings.dry_run:
        logger.info("DRY RUN: would upload %s with metadata %s", video_path, body)
        return None

    async def attempt() -> str:
        return await asyncio.to_thread(_upload_once, video_path, body, settings)

    video_id = await retry_with_backoff(
        attempt,
        max_attempts=settings.retry_max_attempts,
        base_delay=settings.retry_base_seconds,
        max_delay=settings.retry_max_seconds,
    )
    logger.info("YouTube upload complete: %s", video_id)
    return video_id


def script_hash(script: ShortsScript) -> str:
    """Return a stable SHA-256 hash for history tracking."""
    return hashlib.sha256(script.full_script().encode("utf-8")).hexdigest()
