import subprocess
from pathlib import Path

import pytest

from vadibook import fetch
from vadibook.models import Episode, EpisodePart


def make_tone(path: Path, seconds: float) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-ac", "1", "-ar", "16000", str(path)],
        check=True,
    )
    return path


def test_probe_duration_reads_ffprobe(tmp_path):
    wav = make_tone(tmp_path / "t.wav", 2.0)
    assert fetch.probe_duration(wav) == pytest.approx(2.0, abs=0.05)


def test_download_part_skips_existing_file(data_root, monkeypatch):
    from vadibook.paths import audio_path

    existing = audio_path("kv-001", 1)
    existing.write_bytes(b"not really opus")

    def boom(*a, **k):
        raise AssertionError("yt-dlp must not be called when the file exists")

    monkeypatch.setattr(fetch, "_download", boom)
    assert fetch.download_part("abc", "kv-001", 1) == existing


def test_fetch_episode_measures_durations_and_offsets(data_root, monkeypatch):
    from vadibook.paths import audio_path

    def fake_download(yt_id, out, sleep):
        make_tone(out.with_suffix(".wav"), 1.5 if yt_id == "a" else 2.5)
        out.with_suffix(".wav").rename(out)  # test only cares about the path existing

    monkeypatch.setattr(fetch, "_download", fake_download)
    monkeypatch.setattr(fetch, "probe_duration", lambda p: 1.5 if p.name.endswith("p1.opus") else 2.5)
    ep = Episode(series="kv", no=1, parts=[EpisodePart(yt_id="a", title="1"), EpisodePart(yt_id="b", title="2")])
    out = fetch.fetch_episode(ep)
    assert audio_path("kv-001", 1).exists() and audio_path("kv-001", 2).exists()
    assert out.parts[0].duration_sec == 1.5 and out.parts[0].offset_sec == 0.0
    assert out.parts[1].duration_sec == 2.5 and out.parts[1].offset_sec == 1.5
