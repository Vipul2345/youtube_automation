"""Local history ledger used for topic deduplication."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Entry = dict[str, str]


def history_path(state_dir: Path) -> Path:
    return state_dir / "history.json"


def read_history(state_dir: Path) -> list[Entry]:
    """Read history, treating a missing ledger as empty."""
    path = history_path(state_dir)
    if not path.exists():
        return []
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read history ledger: {path}") from exc
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("History ledger must contain a JSON list of objects")
    return [
        {
            "timestamp": str(item.get("timestamp", "")),
            "topic": str(item.get("topic", "")),
            "title": str(item.get("title", "")),
            "script_hash": str(item.get("script_hash", "")),
        }
        for item in data
    ]


def write_history(state_dir: Path, entries: list[Entry]) -> Path:
    """Atomically write the history ledger."""
    state_dir.mkdir(parents=True, exist_ok=True)
    destination = history_path(state_dir)
    payload = json.dumps(entries, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=state_dir, prefix="history.", suffix=".tmp", delete=False
    ) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    temporary_path.replace(destination)
    return destination


def append_history(
    state_dir: Path, topic: str, title: str, script_hash: str, limit: int = 60
) -> Entry:
    """Append one generated item and retain only the most recent entries."""
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "topic": topic,
        "title": title,
        "script_hash": script_hash,
    }
    entries = read_history(state_dir)
    entries.append(entry)
    write_history(state_dir, entries[-limit:])
    return entry


def recent_topics_and_hashes(state_dir: Path, limit: int = 60) -> tuple[list[str], list[str]]:
    """Return recent topics and script hashes for the generation prompt."""
    entries = read_history(state_dir)[-limit:]
    return (
        [entry["topic"] for entry in entries if entry["topic"]],
        [entry["script_hash"] for entry in entries if entry["script_hash"]],
    )
