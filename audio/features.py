from __future__ import annotations

from typing import Tuple

import numpy as np
from scipy.ndimage import median_filter


def compute_instrumental_score(
    stft: np.ndarray,
    rms: np.ndarray,
    spectral_flux: np.ndarray,
    sr: int,
    n_fft: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute a per-frame instrumental score and binary segments.

    Heuristic:
    - vocal_energy_ratio = mid-band energy (300-3000Hz) / total energy
    - stability = 1 - normalized local variance of RMS (low variance -> instrumental)
    - spectral activity: high flux -> voice/articulation

    Returns (score, segments) where score in [0,1] (higher -> more instrumental)
    and segments is uint8 array where 1 == instrumental, 0 == vocal.
    """
    # frequencies for rfft bins
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)

    # band masks
    mid_mask = (freqs >= 300) & (freqs <= 3000)

    # energy per band per frame (stft is frames x bins)
    total_energy = np.sum(stft, axis=1) + 1e-8
    mid_energy = np.sum(stft[:, mid_mask], axis=1) + 1e-8

    vocal_ratio = mid_energy / total_energy  # higher -> more vocal

    # stability: low variance in local window implies instrumental
    win = max(1, int(sr / (n_fft // 2)))  # approx 1 second window in frames
    if win % 2 == 0:
        win += 1

    # local std of RMS
    pad = win // 2
    padded = np.pad(rms, pad, mode="reflect")
    local_std = np.array([
        np.std(padded[i : i + win]) for i in range(len(rms))
    ]) + 1e-8
    # normalize std to [0,1]
    local_std_norm = (local_std - local_std.min()) / (local_std.max() - local_std.min() + 1e-8)
    stability = 1.0 - local_std_norm

    # normalize spectral flux
    flux = spectral_flux
    flux_norm = (flux - flux.min()) / (flux.max() - flux.min() + 1e-8)

    # combine: favor stability and low vocal_ratio and low flux
    score = 0.5 * stability + 0.35 * (1.0 - vocal_ratio) + 0.15 * (1.0 - flux_norm)
    score = np.clip(score, 0.0, 1.0)

    # smooth and median filter to get coherent segments
    score_smooth = median_filter(score, size=3)
    segments = (score_smooth > 0.6).astype("uint8")

    return score_smooth.astype("float32"), segments
