from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE = Path("audio/cache")
BASE.mkdir(parents=True, exist_ok=True)


def get_audio_cache_path(video_id: str) -> Path:
    return BASE / f"{video_id}.wav"


def get_analysis_cache_path(video_id: str) -> Path:
    return BASE / f"{video_id}.npz"


def get_meta_path(video_id: str) -> Path:
    return BASE / f"{video_id}.json"


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            data = fh.read(8192)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def load_meta(video_id: str) -> dict[str, Any] | None:
    p = get_meta_path(video_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_meta(video_id: str, meta: dict[str, Any]) -> None:
    p = get_meta_path(video_id)
    p.write_text(json.dumps(meta, indent=2), encoding="utf-8")
