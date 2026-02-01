from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def load_wav(path: Path, sr: int = 44100) -> Tuple[np.ndarray, int]:
    """Load audio as mono float32 numpy array (shape: n_samples,) and ensure sample rate sr.

    Uses `soundfile` for reading and `resample_poly` if resampling needed.
    """
    data, file_sr = sf.read(str(path), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)

    if file_sr != sr:
        # resample with polyphase resampler
        gcd = np.gcd(file_sr, sr)
        up = sr // gcd
        down = file_sr // gcd
        data = resample_poly(data, up, down)

    return data.astype("float32"), sr


def save_wav(path: Path, data: np.ndarray, sr: int = 44100) -> None:
    sf.write(str(path), data, sr, subtype="PCM_16")
