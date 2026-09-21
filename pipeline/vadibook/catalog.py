"""Stage 1: turn the two official playlists into data/public/episodes.json."""

from __future__ import annotations

import json
import re

from vadibook.models import Episode, EpisodePart
from vadibook.paths import episodes_file, public_dir

# (series, playlist url). Both channels are verified Pana Film channels:
#   @KurtlarVadisiOfficial (Kurtlar Vadisi, 2003-2005) and @KurtlarVadisi (Kurtlar Vadisi Pusu).
PLAYLISTS: list[tuple[str, str]] = [
    ("kv", "https://www.youtube.com/playlist?list=PLN6a-WhvxvGJEdiaoCuF3wAHi5TL9Tif9"),  # KV 1-55
    ("kv", "https://www.youtube.com/playlist?list=PLOFoevjhe1HU-FncKpm_OTiSWdTbA7nfh"),  # KV 57-97
    ("pusu", "https://www.youtube.com/playlist?list=PLOFoevjhe1HX4HquOBEASUtK_DTfqJSMX"),  # Pusu 1-300
]
EXPECTED: dict[str, int] = {"kv": 97, "pusu": 300}

# "123. Bölüm", "123.Bölüm", "123 Bölüm" (case/diacritic-insensitive) or "Episode 123"
_EPISODE_RE = re.compile(
    r"(?<!\d)(\d{1,3})\s*\.?\s*B[öÖo]L[üÜu]M|Episode\s+(\d{1,3})(?!\d)", re.IGNORECASE
)
# "2. Kısım"
_PART_RE = re.compile(r"(?<!\d)(\d{1,2})\s*\.?\s*K[ıİi]S[ıİi]M", re.IGNORECASE)
_PUSU_RE = re.compile(r"pusu", re.IGNORECASE)


def parse_title(title: str, default_series: str) -> tuple[str, int, int | None] | None:
    """Return (series, episode_no, part_no) or None when the title is not an episode."""
    m = _EPISODE_RE.search(title)
    if not m:
        return None
    no = int(m.group(1) or m.group(2))
    series = "pusu" if _PUSU_RE.search(title) else default_series
    pm = _PART_RE.search(title)
    return series, no, int(pm.group(1)) if pm else None


def fetch_playlist(url: str) -> list[dict]:
    """Flat playlist listing via yt-dlp: id, title, duration (seconds, may be None)."""
    import yt_dlp  # imported lazily so unit tests never touch the network

    opts = {"extract_flat": "in_playlist", "quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = []
    for e in info.get("entries") or []:
        if not e:
            continue
        entries.append({"id": e["id"], "title": e.get("title") or "", "duration": e.get("duration")})
    return entries


def extra_file():
    """Official-channel videos that are not in any playlist, added by hand (see README)."""
    return public_dir() / "catalog_extra.json"


def load_extra() -> list[dict]:
    p = extra_file()
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def build_catalog(
    entries_by_series: dict[str, list[dict]], extra: list[dict] | None = None
) -> tuple[list[Episode], list[str]]:
    """Group flat entries into episodes (with ordered parts). Returns (episodes, warnings).

    `extra` entries ({"series","no","parts":[{"yt_id","title"}]}) fill episodes the playlists lack.
    """
    buckets: dict[tuple[str, int], list[tuple[int | None, dict]]] = {}
    warnings: list[str] = []
    for default_series, entries in entries_by_series.items():
        for e in entries:
            parsed = parse_title(e["title"], default_series)
            if parsed is None:
                warnings.append(f"unparsed: {e['id']} {e['title']!r}")
                continue
            series, no, part = parsed
            buckets.setdefault((series, no), []).append((part, e))

    episodes: list[Episode] = []
    for (series, no), items in sorted(buckets.items()):
        if len(items) > 1 and any(part is None for part, _ in items):
            ids = ", ".join(e["id"] for _, e in items)
            warnings.append(
                f"duplicate: {series}/{no} has {len(items)} videos without part numbers ({ids}); keeping first"
            )
            items = items[:1]
        items.sort(key=lambda it: it[0] or 1)
        parts: list[EpisodePart] = []
        offset = 0.0
        for _, e in items:
            dur = float(e["duration"]) if e.get("duration") else None
            parts.append(EpisodePart(yt_id=e["id"], title=e["title"], offset_sec=offset, duration_sec=dur))
            offset += dur or 0.0
        episodes.append(Episode(series=series, no=no, parts=parts))  # type: ignore[arg-type]

    have = {(e.series, e.no) for e in episodes}
    for item in extra or []:
        ep = Episode.model_validate(item)
        if (ep.series, ep.no) in have:
            warnings.append(f"extra ignored: {ep.id} already comes from a playlist")
            continue
        episodes.append(ep)
    episodes.sort(key=lambda e: (e.series, e.no))
    return episodes, warnings


def gaps(episodes: list[Episode], expected: dict[str, int] = EXPECTED) -> list[str]:
    have = {(e.series, e.no) for e in episodes}
    return [f"{s}/{n}" for s, count in expected.items() for n in range(1, count + 1) if (s, n) not in have]


def save_episodes(episodes: list[Episode]) -> None:
    payload = [e.model_dump() for e in episodes]
    episodes_file().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_episodes() -> list[Episode]:
    p = episodes_file()
    if not p.exists():
        raise FileNotFoundError(f"{p} yok — önce `vadibook catalog` çalıştır")
    return [Episode.model_validate(x) for x in json.loads(p.read_text(encoding="utf-8"))]


def find_episode(episodes: list[Episode], ep_id: str) -> Episode:
    for e in episodes:
        if e.id == ep_id:
            return e
    raise KeyError(f"bölüm bulunamadı: {ep_id}")
