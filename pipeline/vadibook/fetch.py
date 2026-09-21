"""Stage 2: download audio only (never video) plus YouTube's auto Turkish subtitles as a backup source."""

from __future__ import annotations

import subprocess
from pathlib import Path

from vadibook.models import Episode
from vadibook.paths import audio_path


def _download(yt_id: str, out: Path, sleep: float) -> None:
    import yt_dlp  # lazy: keeps unit tests offline

    opts = {
        "format": "bestaudio/best",
        # yt-dlp fills %(ext)s with the source container; the postprocessor then writes <stem>.opus
        "outtmpl": str(out.with_suffix("")) + ".%(ext)s",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "opus"}],
        "writeautomaticsub": True,
        "subtitleslangs": ["tr"],
        "subtitlesformat": "vtt",
        "sleep_interval": sleep,
        "max_sleep_interval": sleep * 2,
        "retries": 5,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={yt_id}"])


def download_part(yt_id: str, key: str, part_no: int, *, sleep: float = 5.0) -> Path:
    out = audio_path(key, part_no)
    if out.exists() and out.stat().st_size > 0:
        return out
    _download(yt_id, out, sleep)
    if not out.exists():
        raise RuntimeError(f"yt-dlp finished but {out} is missing (postprocessor/ffmpeg problem?)")
    return out


def probe_duration(path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(res.stdout.strip())


def fetch_episode(ep: Episode, *, sleep: float = 5.0) -> Episode:
    """Download every part; return a copy whose parts carry measured durations and offsets."""
    parts = []
    offset = 0.0
    for i, part in enumerate(ep.parts, start=1):
        path = download_part(part.yt_id, ep.key, i, sleep=sleep)
        dur = probe_duration(path)
        parts.append(part.model_copy(update={"duration_sec": dur, "offset_sec": offset}))
        offset += dur
    return ep.model_copy(update={"parts": parts})
