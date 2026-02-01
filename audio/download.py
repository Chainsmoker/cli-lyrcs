from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List

CACHE_DIR = Path("audio/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

@dataclass
class VideoResult:
    id: str
    title: str
    uploader: str
    duration: float


def search_youtube(query: str, max_results: int = 5) -> List[VideoResult]:
    """Search YouTube (yt-dlp) and return top results as VideoResult.

    Uses `yt-dlp "ytsearch{N}:{query}" --dump-json` and parses each JSON line.
    """
    cmd = ["yt-dlp", f"ytsearch{max_results}:{query}", "--dump-json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = proc.stdout.strip()
    if not out:
        return []

    results: List[VideoResult] = []
    for line in out.splitlines():
        try:
            obj = json.loads(line)
            vid = obj.get("id") or obj.get("webpage_url")
            title = obj.get("title", "")
            uploader = obj.get("uploader", obj.get("uploader_id", ""))
            duration = float(obj.get("duration", 0.0) or 0.0)
            if not vid:
                continue
            results.append(VideoResult(str(vid), title, uploader, duration))
        except Exception:
            continue
    return results


def download_audio(video_id: str) -> Path:
    """Download audio for a given video id (or url) and convert to WAV.

    Result is saved to `audio/cache/<video_id>.wav`. If already present, it is not re-downloaded.
    """
    out_wav = CACHE_DIR / f"{video_id}.wav"
    if out_wav.exists():
        return out_wav

    # Use yt-dlp to extract audio and convert to wav via ffmpeg
    # -x: extract audio, --audio-format wav
    cmd = [
        "yt-dlp",
        "-f",
        "bestaudio",
        "--extract-audio",
        "--audio-format",
        "wav",
        "--output",
        str((CACHE_DIR / "%(id)s.%(ext)s").as_posix()),
        video_id,
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    if out_wav.exists():
        return out_wav

    raise FileNotFoundError(f"Failed to download audio for {video_id}")


def download_thumbnail(video_id: str, title: str | None = None, artist: str | None = None) -> Path | None:
    """Download a thumbnail for the given video.

    Strategy:
    1. If `title` and `artist` are provided, try the iTunes Search API to get album artwork (prefer\n       the higher-resolution variant of `artworkUrl100`).
    2. Fallback to the existing `yt-dlp` thumbnail extraction if the above fails.

    Returns the saved Path or None if no thumbnail could be obtained.
    """
    out_img = CACHE_DIR / f"{video_id}.jpg"
    if out_img.exists():
        return out_img

    # Try iTunes search first (prefer album artwork)
    if title and artist:
        try:
            import requests

            query = f"{artist} {title}"
            r = requests.get("https://itunes.apple.com/search", params={"term": query, "media": "music", "limit": 1}, timeout=8)
            r.raise_for_status()
            data = r.json()
            if data.get("resultCount", 0) > 0 and data.get("results"):
                art100 = data["results"][0].get("artworkUrl100")
                if art100:
                    # derive larger size (1000x1000) from artworkUrl100
                    large = art100.replace("100x100bb", "1000x1000bb")
                    try:
                        img_r = requests.get(large, timeout=8)
                        img_r.raise_for_status()
                        out_img.write_bytes(img_r.content)
                        return out_img
                    except Exception:
                        # fall through to yt-dlp fallback
                        pass
        except Exception:
            pass

    # Fallback: use yt-dlp's thumbnail extraction
    cmd = [
        "yt-dlp",
        f"https://www.youtube.com/watch?v={video_id}",
        "--skip-download",
        "--write-thumbnail",
        "--convert-thumbnails",
        "jpg",
        "-o",
        str((CACHE_DIR / "%(id)s").as_posix()),
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    if out_img.exists():
        return out_img
    return None
