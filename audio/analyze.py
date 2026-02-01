from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import numpy as np
from numpy.fft import rfft

from .io import load_wav
from .cache import get_analysis_cache_path, write_meta, checksum


@dataclass
class AnalysisResult:
    rms: np.ndarray
    stft: np.ndarray  # magnitude spectrogram (frames x bins)
    spectral_flux: np.ndarray
    energy: np.ndarray
    beats: np.ndarray  # frame indices of detected beats


def _frame_signal(x: np.ndarray, n_fft: int, hop: int) -> np.ndarray:
    n_frames = 1 + (len(x) - n_fft) // hop
    frames = np.lib.stride_tricks.as_strided(
        x,
        shape=(n_frames, n_fft),
        strides=(x.strides[0] * hop, x.strides[0]),
    )
    return frames.copy()


def analyze(video_id: str, wav_path: Path, sr: int = 44100, n_fft: int = 1024, hop: int = 512) -> Dict[str, object]:
    """Perform offline analysis and save results to cache.

    Computes RMS per frame, magnitude STFT (rfft), spectral flux, total energy, a simple peak-based beat list,
    and an instrumental score. If a valid cache with matching checksum/params exists, it will be reused.
    """
    out = get_analysis_cache_path(video_id)
    meta_path = get_analysis_cache_path(video_id).with_suffix(".json")

    # skip if cache exists and meta matches
    try:
        existing = load_meta(video_id)
        if existing and existing.get("sha256") == checksum(wav_path) and existing.get("n_fft") == n_fft and existing.get("hop") == hop and existing.get("sr") == sr:
            return existing
    except Exception:
        pass

    data, file_sr = load_wav(wav_path, sr=sr)
    # pad if necessary
    if len(data) < n_fft:
        data = np.pad(data, (0, n_fft - len(data)))

    frames = _frame_signal(data, n_fft, hop)
    window = np.hanning(n_fft)
    windowed = frames * window

    stft = np.abs(rfft(windowed, axis=1))

    # RMS per frame
    rms = np.sqrt(np.mean(windowed ** 2, axis=1))

    # energy per frame
    energy = np.sum(windowed ** 2, axis=1)

    # spectral flux: positive difference in magnitude spectrum
    spec_diff = np.diff(stft, axis=0)
    spec_diff[spec_diff < 0] = 0
    spectral_flux = np.sum(spec_diff, axis=1)
    spectral_flux = np.concatenate(([0.0], spectral_flux))

    # simple beat detection: pick peaks in spectral_flux that exceed local median * factor
    from scipy.signal import find_peaks

    if spectral_flux.size > 0:
        med = np.median(spectral_flux)
        peaks, _ = find_peaks(spectral_flux, height=med * 1.5, distance= int(0.15 * sr / hop))
    else:
        peaks = np.array([], dtype=int)

    # compute instrumental score
    from .features import compute_instrumental_score

    instr_score, segments = compute_instrumental_score(stft, rms, spectral_flux, sr=sr, n_fft=n_fft)

    # Save to .npz
    np.savez_compressed(
        out,
        rms=rms.astype(np.float32),
        stft=stft.astype(np.float32),
        spectral_flux=spectral_flux.astype(np.float32),
        energy=energy.astype(np.float32),
        beats=peaks.astype(np.int32),
        instrumental=instr_score.astype(np.float32),
        segments=segments.astype(np.uint8),
    )

    # write meta
    meta = {
        "source_wav": str(wav_path),
        "sha256": checksum(wav_path),
        "n_fft": n_fft,
        "hop": hop,
        "sr": sr,
    }
    write_meta(video_id, meta)

    return meta
