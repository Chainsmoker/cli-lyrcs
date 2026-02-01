from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
import soundfile as sf


class Player:
    """A minimal player backed by sounddevice that exposes monotonic time for sync.

    Usage:
        p = Player()
        p.load(path)
        p.play()
        p.current_time()
        p.stop()
    """

    def __init__(self) -> None:
        self._data: np.ndarray | None = None
        self._sr: int | None = None
        self._start: float | None = None
        self._stream: sd.RawOutputStream | None = None
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()

    def load(self, path: Path) -> None:
        data, sr = sf.read(str(path), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        self._data = data
        self._sr = sr

    def _playback_thread(self) -> None:
        assert self._data is not None and self._sr is not None
        self._stop_flag.clear()
        self._start = time.monotonic()
        sd.play(self._data, samplerate=self._sr)
        # block until finished or stopped
        while sd.get_stream() is not None and not self._stop_flag.is_set():
            time.sleep(0.05)
        sd.stop()
        self._start = None

    def play(self) -> None:
        if self._data is None:
            raise RuntimeError("No audio loaded")
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._playback_thread, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag.set()
        sd.stop()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._start = None

    def current_time(self) -> float:
        if self._start is None:
            return 0.0
        return time.monotonic() - self._start

    def is_playing(self) -> bool:
        return self._start is not None
