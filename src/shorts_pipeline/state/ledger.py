"""Crash-recovery publication ledger.

This is intentionally separate from ``history.json``: history is editorial
deduplication data, while this file is an operational record of upload intent.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

Stage = Literal[
    "planned",
    "scripted",
    "rendered",
    "validated",
    "uploading",
    "uploaded",
    "published",
    "failed",
    "review_required",
    "upload_outcome_unknown",
]


def ledger_path(state_dir: Path) -> Path:
    return state_dir / "publication_ledger.json"


def receipt_path(state_dir: Path, publication_id: str) -> Path:
    safe_id = hashlib.sha256(publication_id.encode("utf-8")).hexdigest()[:24]
    return state_dir / f"upload-receipt-{safe_id}.json"


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as fh:
        json.dump(value, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
        temporary = Path(fh.name)
        fh.flush()
        os.fsync(fh.fileno())
    temporary.replace(path)


def read_ledger(state_dir: Path) -> list[dict[str, Any]]:
    path = ledger_path(state_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Unable to read publication ledger") from exc
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("Publication ledger must contain a JSON list of objects")
    return data


def stable_publication_id(channel: str, slot: str) -> str:
    """Return an ID stable across delayed/retried workflow starts."""
    digest = hashlib.sha256(f"{channel.strip().casefold()}\0{slot.strip()}".encode()).hexdigest()
    return f"pub-{digest[:24]}"


def find_active(state_dir: Path, publication_id: str) -> dict[str, Any] | None:
    for item in reversed(read_ledger(state_dir)):
        if item.get("publication_id") == publication_id and item.get("stage") not in {
            "failed",
            "published",
        }:
            return item
    return None


def record(state_dir: Path, entry: dict[str, Any], stage: Stage, **updates: Any) -> dict[str, Any]:
    entries = read_ledger(state_dir)
    current = dict(entry)
    current.update(updates)
    current["stage"] = stage
    current["updated_at"] = datetime.now(UTC).isoformat()
    entries = [
        item for item in entries if item.get("publication_id") != current.get("publication_id")
    ]
    entries.append(current)
    _write(ledger_path(state_dir), entries[-200:])
    return current


def new_intent(
    state_dir: Path, publication_id: str, execution_id: str, script_hash: str
) -> dict[str, Any]:
    existing = find_active(state_dir, publication_id)
    if existing:
        raise RuntimeError(
            f"Publication {publication_id} is already {existing.get('stage')}; "
            "reconcile it before retrying"
        )
    return record(
        state_dir,
        {
            "publication_id": publication_id,
            "execution_id": execution_id,
            "script_hash": script_hash,
            "created_at": datetime.now(UTC).isoformat(),
        },
        "planned",
    )


def write_receipt(state_dir: Path, entry: dict[str, Any], **updates: Any) -> Path:
    receipt = {
        "publication_id": entry.get("publication_id"),
        "execution_id": entry.get("execution_id"),
        "script_hash": entry.get("script_hash"),
        "youtube_video_id": entry.get("youtube_video_id"),
        "requested_visibility": entry.get("requested_visibility"),
        "observed_visibility": entry.get("observed_visibility"),
        "stage": entry.get("stage"),
        "written_at": datetime.now(UTC).isoformat(),
        **updates,
    }
    path = receipt_path(state_dir, str(entry["publication_id"]))
    _write(path, receipt)
    return path
