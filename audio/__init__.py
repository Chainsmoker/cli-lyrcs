"""audio package: download + io + analysis utilities."""
from .download import search_youtube, download_audio
from .io import load_wav, save_wav
from .analyze import analyze
from .cache import get_audio_cache_path, get_analysis_cache_path

__all__ = [
    "search_youtube",
    "download_audio",
    "load_wav",
    "save_wav",
    "analyze",
    "get_audio_cache_path",
    "get_analysis_cache_path",
]
