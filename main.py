import time
import subprocess
from pathlib import Path
import math
import argparse
import os
import sys

import requests
from urllib.parse import quote

from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich.box import ROUNDED



# =========================
# CONFIG
# =========================
TRACK = "hey brother"
ARTIST = "avicii"
COVER_PATH = Path("cover.jpg")

# 🔹 COVER MÁS PEQUEÑO
ASCII_WIDTH = 36     # <-- CAMBIO
ASCII_HEIGHT = 15    # <-- CAMBIO

LEFT_COL_WIDTH = ASCII_WIDTH

GAP_TRIGGER = 3.0
WAVE_HEIGHT = 6

# Minimum continuous instrumental duration (seconds) required to show visualizer.
MIN_INSTRUMENTAL_SEC = float(os.environ.get("MIN_INSTRUMENTAL_SEC", 4.0))
# Merge small instrumental gaps shorter than this (seconds)
MIN_INSTRUMENTAL_GAP_SEC = float(os.environ.get("MIN_INSTRUMENTAL_GAP_SEC", 0.5))
# Fraction of frames in window that must be instrumental to mark region
MIN_INSTRUMENTAL_FRACTION = float(os.environ.get("MIN_INSTRUMENTAL_FRACTION", 0.7))
# Window (seconds) around an LRC timestamp considered vocal; used to suppress visualizer.
LYRIC_WINDOW = float(os.environ.get("LYRIC_WINDOW", 1.2))

CP437_GRADIENT = "█▓▒░ "

LEFT_IDLE_BORDER = "cyan"
RIGHT_IDLE_BORDER = "magenta"

BORDER_STYLES = [
    "red",
    "orange1",
    "yellow1",
    "chartreuse1",
    "green",
    "spring_green1",
    "cyan",
    "deep_sky_blue1",
    "dodger_blue1",
    "blue",
    "purple",
    "magenta",
    "hot_pink",
]

WAVE_CHARS = " ▁▂▃▄▅▆▇█"
WAVE_GRADIENT = ["cyan", "deep_sky_blue1", "magenta", "hot_pink"]

console = Console()


def check_deps() -> None:
    try:
        import requests  # noqa: F401
        import numpy  # noqa: F401
        import soundfile  # noqa: F401
        import sounddevice  # noqa: F401
        import yt_dlp  # noqa: F401
    except Exception as exc:  # pragma: no cover - helpful dev error
        console.print(f"[bold red]Missing dependency:[/bold red] {exc}")
        console.print("Install dependencies: `pip install -r requirements.txt` or `pip install -e .`")
        raise

LRC_TIMESTAMPS: list[float] | None = None


# =========================
# HELPERS
# =========================
def animated_border_style(frame: int) -> str:
    return BORDER_STYLES[(frame // 2) % len(BORDER_STYLES)]


def choose_lyrics_source() -> str:
    console.print("Choose lyrics source:\n1) lrclib (default)\n2) ytm")

    try:
        choice = console.input("Choice [1/2]: ").strip()
    except Exception:
        choice = ""

    return "ytm" if choice == "2" else "lrclib"


# =========================
# LYRICS
# =========================
def fetch_lyrics_lrclib(track: str, artist: str) -> list[str]:
    try:
        r = requests.get(
            "https://lrclib.net/api/search",
            params={"track_name": track, "artist_name": artist},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return ["Lyrics not found"]

    if not data:
        return ["Lyrics not found"]

    return data[0].get("plainLyrics", "").splitlines() or ["Lyrics not found"]


def fetch_lyrics_ytm(track: str, artist: str) -> list[str]:
    query = f"{artist} {track}"
    url = "https://ytm.nwvbug.com/request-lyrics/" + quote(query)

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return ["Lyrics not found"]

    lrc = data.get("lrc")
    if isinstance(lrc, list):
        global LRC_TIMESTAMPS
        LRC_TIMESTAMPS = [float(x["time"]) for x in lrc if "time" in x]
        return [x.get("text", "") for x in lrc]

    return ["Lyrics not found"]


def fetch_lyrics(track: str, artist: str, source: str) -> list[str]:
    return fetch_lyrics_ytm(track, artist) if source == "ytm" else fetch_lyrics_lrclib(track, artist)


def input_plan() -> list[str]:
    """Prompt the user to paste JSON containing an "lrc" array.

    Finish paste with an empty line. Example format:
    {
      "lrc": [ {"text": "...", "time": 3.01}, ... ],
      "source": "ytm"
    }
    """
    console.print("Paste JSON with an `lrc` array (finish with an empty line).")

    lines: list[str] = []
    while True:
        try:
            line = console.input()
        except Exception:
            break
        if not line.strip():
            break
        lines.append(line)

    if not lines:
        console.print("No input provided; using fallback.")
        return ["Lyrics not found"]

    import json
    try:
        data = json.loads("\n".join(lines))
    except Exception as exc:
        console.print(f"[red]Invalid JSON:[/red] {exc}")
        return ["Lyrics not found"]

    lrc = data.get("lrc")
    if isinstance(lrc, list):
        global LRC_TIMESTAMPS
        # Preserve positional alignment: record None when a line has no time
        LRC_TIMESTAMPS = [float(x["time"]) if "time" in x else None for x in lrc]
        return [x.get("text", "") for x in lrc]

    console.print("JSON did not contain a valid 'lrc' list.")
    return ["Lyrics not found"]


def choose_and_get_lyrics() -> list[str]:
    console.print("Choose lyrics source:\n1) lrclib (default)\n2) ytm\n3) plan (paste JSON)")
    try:
        choice = console.input("Choice [1/2/3]: ").strip()
    except Exception:
        choice = ""

    if choice == "3":
        return input_plan()

    return fetch_lyrics(TRACK, ARTIST, "ytm") if choice == "2" else fetch_lyrics(TRACK, ARTIST, "lrclib")


def clean_title_artist(title: str, artist: str) -> tuple[str, str]:
    """Normalize title and artist strings for display and metadata.

    - Remove parenthetical/bracketed content ("(Official Video)", "[Lyric Video]", ...)
    - Strip common tags like "official video", "lyrics", "audio", "HD", etc.
    - Remove featuring/ft/feat blocks and the following artist names.
    - If the uploader/artist string appears as a prefix or suffix in the title ("Artist - Title"), remove it.
    Returns (clean_title, artist) where artist is left as the uploader.
    """
    import re

    t = (title or "").strip()
    a = (artist or "").strip()

    # Remove bracketed/parenthetical phrases
    t = re.sub(r"\s*[\(\[\{][^\)\]\}]*[\)\]\}]\s*", " ", t)

    # Remove common noisy tags
    t = re.sub(r"(?i)\b(official (music )?video|official|lyrics|lyric video|audio|hd|hq|remaster(ed)?|with lyrics|radio edit)\b", "", t)

    # Remove feat/ft/featuring + following artist list
    t = re.sub(r"(?i)\b(?:ft|feat|featuring)\.?[:\-]?\s*[^-–|()\[\]]+", "", t)

    # If uploader appears in title as prefix/suffix remove it
    if a:
        patt = re.escape(a)
        t = re.sub(rf"(?i)^\s*{patt}\s*[-–:|]\s*", "", t)
        t = re.sub(rf"(?i)\s*[-–:|]\s*{patt}\s*$", "", t)

    # Remove stray separators and collapse whitespace
    t = re.sub(r"\s*[-–:|]\s*", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    # Trim surrounding quotes
    t = t.strip('"\'')

    return (t or title, a or artist)


# =========================
# COVER
# =========================
def download_cover(track: str, artist: str, output: Path):
    if output.exists():
        return

    subprocess.run(
        [
            "yt-dlp",
            f"ytsearch1:{artist} {track}",
            "--skip-download",
            "--write-thumbnail",
            "--convert-thumbnails",
            "jpg",
            "-o",
            str(output.with_suffix("")),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )



# =========================
# IMAGE → ASCII
# =========================
# Old ASCII conversion removed. `visual.cover.render_cover_ascii` provides a simple editable box.
# Old ASCII conversion removed. `visual.cover.render_cover_ascii` provides a simple editable box.


# =========================
# PLAYER
# =========================
def fmt_time(sec: float) -> str:
    return f"{int(sec)//60:02}:{int(sec)%60:02}"


def render_player(title, artist, cur, total, width):
    bar_w = width - 24
    filled = int((cur / total) * bar_w)
    bar = "█" * filled + "-" * (bar_w - filled)

    return "\n".join(
        [
            title.center(width),
            artist.center(width),
            "",
            f"< Prev [{bar}] Next >".center(width),
            f"{fmt_time(cur)} / {fmt_time(total)}".center(width),
        ]
    )


# =========================
# LYRICS WINDOW
# =========================
def render_lyrics_window(lyrics, idx, height, width) -> Text:
    text = Text()
    visible = max(1, height // 2)
    start = max(0, idx - visible // 2)
    end = min(len(lyrics), start + visible)

    for i in range(start, end):
        line = lyrics[i].center(width)
        style = "bold cyan" if i == idx else "dim"
        text.append(line + "\n", style=style)

    return text


# Helper: determine lyric index from LRC timestamps
def lyric_index_from_timestamps(elapsed: float, timestamps: list[float | None]) -> int | None:
    """Return the index i such that timestamps[i] <= elapsed < timestamps[next_non_none]

    If a timestamp is None it is skipped. Returns None when no matching interval.
    """
    # quick guard
    if not timestamps:
        return None

    # iterate through timestamps and find interval
    for i, ts in enumerate(timestamps):
        if ts is None:
            continue
        # find next non-None timestamp
        next_ts = None
        for j in range(i + 1, len(timestamps)):
            if timestamps[j] is not None:
                next_ts = timestamps[j]
                break
        if elapsed >= ts and (next_ts is None or elapsed < next_ts):
            return i
        if elapsed < ts:
            # since timestamps are typically increasing, we can stop early
            break
    return None


# =========================
# WAVE
# =========================
def render_wave_ascii(width: int, height: int, phase: float) -> Text:
    text = Text()
    mid = height / 2
    amp = height / 2.2
    freq = 2 * math.pi / (width / 1.6)

    rows = [Text() for _ in range(height)]

    for x in range(width):
        y = mid + math.sin(x * freq + phase) * amp * math.sin(phase / 3)
        y = int(max(0, min(height - 1, y)))

        strength = abs(math.sin(x * freq + phase))
        ch = WAVE_CHARS[int(strength * (len(WAVE_CHARS) - 1))]
        color = WAVE_GRADIENT[int(strength * (len(WAVE_GRADIENT) - 1))]

        rows[y].append(ch, style=color)

    for i, row in enumerate(rows):
        text.append(row)
        if i < height - 1:
            text.append("\n")

    return text


# Layout logic now lives in `ui.layout.build_layout` (keeps UI concerns isolated).

# =========================
# MAIN
# =========================
def _search_and_select() -> object | None:
    q = ""
    try:
        q = console.input("Search (artist/song): ").strip()
    except Exception:
        return None

    if not q:
        return None

    # local import to avoid raising on module import when deps are missing
    from audio.download import search_youtube

    results = search_youtube(q, max_results=5)
    if not results:
        console.print("No results found")
        return None

    for i, r in enumerate(results):
        console.print(f"[{i}] {r.title} — {r.uploader} ({fmt_time(r.duration)})")

    try:
        choice = int(console.input("Choose index [0]: ").strip() or "0")
    except Exception:
        choice = 0

    choice = max(0, min(choice, len(results) - 1))
    return results[choice]


def main():
    console.clear()

    # local imports (delay heavy dependencies until runtime)
    from audio.download import download_audio, download_thumbnail
    from audio.analyze import analyze
    from audio.cache import load_meta, get_analysis_cache_path
    from visual.cover import render_cover_ascii
    from ui.layout import build_layout
    from ui.player import Player
    import numpy as np
    import soundfile as sf

    sel = _search_and_select()
    if sel is None:
        console.print("No selection, exiting.")
        return

    # use selected metadata for lyrics lookup
    global TRACK, ARTIST
    clean_track, clean_artist = clean_title_artist(sel.title, sel.uploader)
    TRACK = clean_track
    ARTIST = clean_artist

    console.print(f"Selected: {TRACK} — {ARTIST}")

    # download audio and thumbnail to cache
    console.print("Downloading audio...")
    wav_path = download_audio(sel.id)
    console.print(f"Audio cached at: {wav_path}")

    console.print("Downloading thumbnail (if available)...")
    thumb = download_thumbnail(sel.id, title=sel.title, artist=sel.uploader)
    if thumb:
        COVER_PATH = Path(thumb)

    # run analysis (idempotent - uses cache)
    console.print("Analyzing audio (once)...")
    analyze(sel.id, wav_path)

    meta = load_meta(sel.id) or {}
    analysis_npz = get_analysis_cache_path(sel.id)

    try:
        arr = np.load(analysis_npz)
        rms = arr["rms"]
        stft = arr["stft"]
        spectral_flux = arr["spectral_flux"]
        beats = arr["beats"] if "beats" in arr else np.zeros(0, dtype=int)
        instrumental = arr["instrumental"] if "instrumental" in arr else np.zeros(len(rms), dtype=np.float32)
        segments = arr["segments"] if "segments" in arr else np.zeros(len(rms), dtype=np.uint8)
        hop = int(meta.get("hop", 512))
        sr = int(meta.get("sr", 44100))

        # Build a robust instrumental mask that avoids flicker:
        # 1) fill small gaps between instrumental runs (<= MIN_INSTRUMENTAL_GAP_SEC)
        # 2) mark frames as 'instrumental_long' when a sliding window of length
        #    MIN_INSTRUMENTAL_SEC contains at least MIN_INSTRUMENTAL_FRACTION instrumentals
        min_inst_frames = max(1, int(math.ceil(MIN_INSTRUMENTAL_SEC * sr / hop)))
        gap_frames = int(math.ceil(MIN_INSTRUMENTAL_GAP_SEC * sr / hop))

        instrumental_mask = (segments.astype(int) != 0) if len(segments) > 0 else np.zeros(0, dtype=bool)
        instrumental_long = np.zeros(len(instrumental_mask), dtype=bool)

        if len(instrumental_mask) > 0:
            # fill small gaps between runs
            padded = np.pad(instrumental_mask.astype(int), (1, 1), constant_values=0)
            diff = np.diff(padded)
            starts = np.where(diff == 1)[0]
            ends = np.where(diff == -1)[0]
            # Merge runs separated by small gaps
            merged_mask = instrumental_mask.astype(int).copy()
            for i in range(len(starts) - 1):
                cur_end = ends[i]
                next_start = starts[i + 1]
                if next_start - cur_end <= gap_frames:
                    merged_mask[cur_end:next_start] = 1

            # fractional window detection: mark frames that have enough instrumentals
            window = np.ones(min_inst_frames, dtype=int)
            conv = np.convolve(merged_mask, window, mode="same")
            threshold = int(math.ceil(MIN_INSTRUMENTAL_FRACTION * min_inst_frames))
            instrumental_long = conv >= threshold
            instrumental_long = instrumental_long.astype(bool)

    except Exception:
        rms = np.zeros(1)
        stft = np.zeros((1, 1))
        spectral_flux = np.zeros(1)
        beats = np.zeros(0, dtype=int)
        instrumental = np.zeros(len(rms), dtype=np.float32)
        segments = np.zeros(len(rms), dtype=np.uint8)
        hop = 512
        sr = 44100

    # Ensure `instrumental_long` is always defined (fallback when analysis failed)
    if 'instrumental_long' not in locals():
        instrumental_long = np.zeros(len(segments), dtype=bool) if len(segments) > 0 else np.zeros(0, dtype=bool)


    # fetch lyrics (user chooses source or paste a plan)
    lyrics = choose_and_get_lyrics()

    cover = render_cover_ascii(COVER_PATH, ASCII_WIDTH, ASCII_HEIGHT)

    # If terminal supports Kitty graphics, attempt to render the real artwork over the cover panel.
    try:
        from visual.cover import display_cover_image

        # Rough pixel sizing: approximate character cell ~8x16 px (adjust if needed)
        pixel_w = ASCII_WIDTH * 8
        pixel_h = ASCII_HEIGHT * 16
        #displayed = display_cover_image(COVER_PATH, pixel_w=pixel_w, pixel_h=pixel_h)
        cover_displayed = bool(displayed)
        if displayed:
            # use a short label in the panel when the image is rendered externally
            cover = "[image]"
    except Exception:
        cover_displayed = False
        pass

    player = Player()
    player.load(wav_path)
    song_len = len(player._data) / player._sr if player._data is not None else 0.0
    player.play()

    lyric_idx = 0
    frame = 0
    last_change = time.monotonic()

    with Live(console=console, refresh_per_second=12, screen=True) as live:
        while True:
            elapsed = player.current_time()
            if elapsed >= song_len:
                break

            # advance lyrics based on LRC timestamps when available
            if LRC_TIMESTAMPS and any(ts is not None for ts in LRC_TIMESTAMPS):
                new_idx = lyric_index_from_timestamps(elapsed, LRC_TIMESTAMPS)
                if new_idx is not None:
                    lyric_idx = min(new_idx, len(lyrics) - 1)
            else:
                # fallback: advance every ~2s for un-timestamped lyrics
                if time.monotonic() - last_change >= 2:
                    lyric_idx = min(lyric_idx + 1, len(lyrics) - 1)
                    last_change = time.monotonic()

            full_w = max(40, console.size.width - 6)
            lyrics_h = max(10, console.size.height - (ASCII_HEIGHT + 8))

            # pick frame index (kept for timestamp alignment)
            frame_idx = min(len(rms) - 1, int((elapsed * sr) / hop)) if len(rms) > 0 else 0

            # detect nearby lyric timestamp (if present)
            lyric_window = LYRIC_WINDOW  # seconds around a lyric time considered "vocal"
            lyric_active = False
            try:
                if LRC_TIMESTAMPS:
                    lyric_active = any((ts is not None) and abs(ts - elapsed) <= lyric_window for ts in LRC_TIMESTAMPS)
            except Exception:
                lyric_active = False

            # Visualizer removed: always show lyrics; no cava text or animation
            cava_text = None
            is_instrumental = False
            show_cava = False

            lyrics_render = render_lyrics_window(lyrics, lyric_idx, lyrics_h, full_w)

            player_str = render_player(TRACK.title(), ARTIST.title(), elapsed, song_len, full_w)

            live.update(
                build_layout(
                    cover,
                    cava_text,
                    lyrics_render,
                    player_str,
                    frame,
                    is_instrumental,
                )
            )

            # keep Kitty-rendered cover visible by re-sending periodically (every 6 frames ≈ 0.5s)
            try:
                if cover_displayed and frame % 6 == 0:
                    from visual.cover import display_cover_image as _display

                    _display(COVER_PATH, pixel_w=pixel_w, pixel_h=pixel_h)
            except Exception:
                # if sending fails, stop trying
                cover_displayed = False

            frame += 1
            time.sleep(0.08)

    player.stop()


if __name__ == "__main__":
    check_deps()
    main()
