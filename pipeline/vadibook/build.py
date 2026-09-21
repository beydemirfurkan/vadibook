"""Stage 6 (Faz 2): utterances → canonical SQLite + Meilisearch documents.

The SQLite file is the contract the web app reads (episodes, per-episode timelines); Meilisearch holds
the same utterances for full-text search. Neither is ever committed or published.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from vadibook import state
from vadibook.models import Episode, Utterance
from vadibook.paths import data_root, utterances_path

MEILI_INDEX = "utterances"
# Meilisearch's tokenizer already folds Turkish diacritics (Kaşifoğlu == kasifoglu, ısı == isi),
# so only `text` is indexed; the SQLite text_norm/text_ascii columns stay for the web app's own use.
MEILI_SETTINGS: dict = {
    "searchableAttributes": ["text"],
    "filterableAttributes": ["series", "ep", "ep_key", "speaker"],
    "sortableAttributes": ["ep", "start"],
    "pagination": {"maxTotalHits": 5000},
}

_SCHEMA = """
create table if not exists episodes (
  key text primary key, series text not null, no integer not null, title text not null,
  yt_id text not null, duration_sec real, parts text not null
);
create table if not exists utterances (
  id text primary key, ep_key text not null, idx integer not null, part integer not null,
  start real not null, end real not null, speaker text not null,
  text text not null, text_norm text not null, text_ascii text not null, yt_url text not null
);
create index if not exists utterances_ep on utterances(ep_key, idx);
create index if not exists utterances_speaker on utterances(ep_key, speaker);
"""


def sqlite_path() -> Path:
    p = data_root() / "private"
    p.mkdir(parents=True, exist_ok=True)
    return p / "vadibook.sqlite"


def yt_url(ep: Episode, part_no: int, start: float) -> str:
    """Deep link into the official upload of the right part, at the episode-global `start`."""
    part = ep.parts[part_no - 1]
    return f"https://youtu.be/{part.yt_id}?t={int(start - part.offset_sec)}"


def _part_no(u: Utterance) -> int:
    return int(u.speaker.split(":", 1)[0][1:])  # "p2:SPEAKER_03" -> 2


def build_sqlite(episodes: list[Episode]) -> dict:
    """Ingest every episode whose `align` stage is done; rows of an episode are replaced, not duplicated."""
    conn = sqlite3.connect(sqlite_path())
    conn.executescript(_SCHEMA)
    n_eps = n_utts = 0
    for ep in episodes:
        if not state.is_done(ep.key, "align"):
            continue
        rows = []
        with utterances_path(ep.key).open(encoding="utf-8") as fh:
            for line in fh:
                u = Utterance.model_validate_json(line)
                part = _part_no(u)
                # Meilisearch document ids allow only [a-zA-Z0-9_-], so no colon here.
                rows.append((
                    f"{ep.key}_{u.idx:06d}", ep.key, u.idx, part, u.start, u.end, u.speaker,
                    u.text, u.text_norm, u.text_ascii, yt_url(ep, part, u.start),
                ))
        with conn:
            conn.execute("delete from utterances where ep_key = ?", (ep.key,))
            conn.execute(
                "insert or replace into episodes values (?,?,?,?,?,?,?)",
                (
                    ep.key, ep.series, ep.no, ep.parts[0].title, ep.parts[0].yt_id,
                    sum(p.duration_sec or 0 for p in ep.parts),
                    json.dumps([p.model_dump() for p in ep.parts], ensure_ascii=False),
                ),
            )
            conn.executemany("insert into utterances values (?,?,?,?,?,?,?,?,?,?,?)", rows)
        n_eps += 1
        n_utts += len(rows)
    conn.close()
    return {"episodes": n_eps, "utterances": n_utts}


def meili_docs(conn: sqlite3.Connection) -> Iterator[dict]:
    q = (
        "select u.id, e.series, e.no, u.ep_key, u.part, u.start, u.end, u.speaker, u.text, u.yt_url "
        "from utterances u join episodes e on e.key = u.ep_key order by u.ep_key, u.idx"
    )
    for r in conn.execute(q):
        yield {
            "id": r[0], "series": r[1], "ep": r[2], "ep_key": r[3], "part": r[4], "start": r[5], "end": r[6],
            "speaker": r[7], "text": r[8], "yt_url": r[9],
        }


def push_meili(url: str, key: str, docs: Iterator[dict], batch: int = 5000) -> int:
    import meilisearch

    client = meilisearch.Client(url, key)
    client.create_index(MEILI_INDEX, {"primaryKey": "id"})
    index = client.index(MEILI_INDEX)
    index.update_settings(MEILI_SETTINGS)
    total = 0
    chunk: list[dict] = []
    for d in docs:
        chunk.append(d)
        if len(chunk) >= batch:
            index.add_documents(chunk)
            total += len(chunk)
            chunk = []
    if chunk:
        index.add_documents(chunk)
        total += len(chunk)
    return total
