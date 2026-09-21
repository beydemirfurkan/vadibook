# vadibook Search MVP (Faz 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A locally runnable site where anyone can search every processed episode's dialogue and jump to the exact second on the official YouTube upload — while the batch pipeline keeps filling `data/private/` in the background.

**Architecture:** A new `build` pipeline stage turns `utterances/*.jsonl` into the canonical SQLite (`data/private/vadibook.sqlite`) and pushes search documents into Meilisearch (Docker). A Next.js 16 app in `web/` reads SQLite server-side for episode pages and proxies search to Meilisearch through `/api/search`, which requests only cropped `_formatted.text` so full dialogue never leaves the server. Speaker labels stay `SPEAKER_xx` until Faz 3.

**Tech Stack:** Python (typer, sqlite3 stdlib, `meilisearch` client) · Meilisearch v1 (Docker) · Next.js 16 App Router + TypeScript + Tailwind v4 · `meilisearch` JS client · `better-sqlite3` · pnpm.

**Spec:** `docs/superpowers/specs/2026-09-21-vadibook-design.md` — sections "8. build", "Web (Next.js)", "Deploy", "Fazlar → Faz 2", "Riskler → Telif".

## Global Constraints

- Full utterance text is never sent to the browser: `/api/search` requests `attributesToRetrieve` without `text*` and returns only `_formatted.text` (crop ≤ 25 words); episode pages render no transcript.
- Only official YouTube uploads are linked: `https://youtu.be/{yt_id}?t={sec}` where `sec = floor(start − part.offset_sec)`.
- Every page carries the fiction disclaimer: "Bu site bir kurgu eserin diyaloglarını indeksler; gerçek kişilere dair ifadeler dizi karakterlerine aittir."
- `build` is idempotent and only ingests episodes whose `align` stage is done; re-running replaces rows for those episodes.
- Meilisearch is reachable only from the Next.js server (never exposed publicly); the web app uses a search-only key.
- Speaker display: `p1:SPEAKER_07` → "Konuşmacı 7" (Faz 3 replaces with character names).
- Turkish UI copy; code identifiers and comments in English.

---

## File Structure

```
pipeline/vadibook/build.py        build_sqlite(), meili_docs(), push_meili(), MEILI_SETTINGS
pipeline/vadibook/cli.py          + `build` command (--push, --meili-url, --meili-key)
pipeline/tests/test_build.py
deploy/docker-compose.yml         meilisearch (+ web service, used in Faz 2 deploy step)
deploy/.env.example               MEILI_MASTER_KEY
web/                              create-next-app (TS, Tailwind, App Router, Turbopack, src/)
web/.env.example                  MEILI_HOST, MEILI_SEARCH_KEY, VADIBOOK_SQLITE
web/src/lib/db.ts                 openDb(), getEpisode(), listEpisodes(), episodeStats(), speakerTimeline(), corpusStats()
web/src/lib/search.ts             search(params) → SearchResult (Meilisearch call, crop-only)
web/src/lib/format.ts             fmtTime(sec), speakerLabel(raw), seriesName(series), ytUrl(...)
web/src/app/layout.tsx            shell: header (logo + search), disclaimer band, footer
web/src/app/page.tsx              hero + stats + example queries
web/src/app/ara/page.tsx          results (server component) + filters + pagination
web/src/app/bolum/[series]/[no]/page.tsx   episode page: embed, stats, speaker timeline, in-episode search
web/src/app/api/search/route.ts   GET proxy (validation, cache headers)
web/src/components/SearchBox.tsx  client component, URL-driven
web/src/components/ResultCard.tsx snippet + meta + YouTube link
web/src/components/SpeakerTimeline.tsx  SVG bars, no text
web/src/components/Disclaimer.tsx
```

---

### Task 1: `build` stage — SQLite + Meilisearch documents

**Files:**
- Create: `pipeline/vadibook/build.py`
- Modify: `pipeline/vadibook/cli.py` (add `build` command), `pipeline/pyproject.toml` (add `meilisearch>=0.33`)
- Test: `pipeline/tests/test_build.py`

**Interfaces:**
- Consumes: `catalog.load_episodes()`, `state.is_done(key, "align")`, `paths.utterances_path(key)`, `models.Utterance`, `models.Episode`.
- Produces: `build.sqlite_path() -> Path` (`data/private/vadibook.sqlite`); `build.yt_url(ep: Episode, part_no: int, start: float) -> str`; `build.build_sqlite(episodes) -> dict` (returns `{"episodes": n, "utterances": m}`; creates tables `episodes(key PK, series, no, title, yt_id, duration_sec, parts TEXT json)` and `utterances(id PK, ep_key, idx, part, start, end, speaker, text, text_norm, text_ascii, yt_url)` + index `(ep_key, idx)`; replaces rows per ingested episode); `build.meili_docs(conn) -> Iterator[dict]` yielding `{id, series, ep, ep_key, part, start, end, speaker, text, text_ascii, yt_url}`; `build.MEILI_INDEX = "utterances"`; `build.MEILI_SETTINGS: dict`; `build.push_meili(url, key, docs, batch=5000) -> int`.
- SQLite schema is the contract for `web/src/lib/db.ts`.

- [ ] **Step 1: Write failing tests** (`pipeline/tests/test_build.py`)

```python
import json
import sqlite3

from vadibook import build, catalog, state
from vadibook.models import Episode, EpisodePart, Utterance, Word
from vadibook.paths import utterances_path


def _ep(series="pusu", no=1, parts=None):
    parts = parts or [EpisodePart(yt_id="abc", title="t", offset_sec=0.0, duration_sec=100.0)]
    return Episode(series=series, no=no, parts=parts)


def _write_utts(ep, rows):
    with utterances_path(ep.key).open("w", encoding="utf-8") as fh:
        for i, (start, end, spk, text) in enumerate(rows):
            u = Utterance(ep=ep.id, idx=i, start=start, end=end, speaker=spk, text=text, text_norm=text.lower(),
                          text_ascii=text.lower(), words=[Word(word=text, start=start, end=end, probability=1)])
            fh.write(u.model_dump_json() + "\n")


def test_yt_url_uses_part_offset():
    ep = _ep(parts=[EpisodePart(yt_id="a", title="", offset_sec=0.0, duration_sec=50.0),
                    EpisodePart(yt_id="b", title="", offset_sec=50.0, duration_sec=50.0)])
    assert build.yt_url(ep, 1, 12.9) == "https://youtu.be/a?t=12"
    assert build.yt_url(ep, 2, 61.2) == "https://youtu.be/b?t=11"


def test_build_sqlite_ingests_only_aligned_episodes_and_is_idempotent(data_root):
    e1, e2 = _ep(no=1), _ep(no=2)
    catalog.save_episodes([e1, e2])
    _write_utts(e1, [(1.0, 2.0, "p1:SPEAKER_00", "Merhaba"), (3.0, 4.0, "p1:SPEAKER_01", "Selam")])
    state.mark_done(e1.key, "align")
    stats = build.build_sqlite([e1, e2])
    assert stats == {"episodes": 1, "utterances": 2}
    stats = build.build_sqlite([e1, e2])  # second run replaces, does not duplicate
    assert stats == {"episodes": 1, "utterances": 2}
    conn = sqlite3.connect(build.sqlite_path())
    assert conn.execute("select count(*) from utterances").fetchone()[0] == 2
    row = conn.execute("select id, ep_key, part, speaker, yt_url from utterances order by idx").fetchone()
    assert row == ("pusu-001:000000", "pusu-001", 1, "p1:SPEAKER_00", "https://youtu.be/abc?t=1")
    ep_row = conn.execute("select series, no, yt_id, duration_sec from episodes").fetchone()
    assert ep_row == ("pusu", 1, "abc", 100.0)


def test_meili_docs_shape(data_root):
    e1 = _ep()
    catalog.save_episodes([e1])
    _write_utts(e1, [(1.0, 2.0, "p1:SPEAKER_00", "Kaşifoğlu nerede")])
    state.mark_done(e1.key, "align")
    build.build_sqlite([e1])
    conn = sqlite3.connect(build.sqlite_path())
    docs = list(build.meili_docs(conn))
    assert docs[0] == {"id": "pusu-001:000000", "series": "pusu", "ep": 1, "ep_key": "pusu-001", "part": 1,
                       "start": 1.0, "end": 2.0, "speaker": "p1:SPEAKER_00", "text": "Kaşifoğlu nerede",
                       "text_ascii": "kaşifoğlu nerede", "yt_url": "https://youtu.be/abc?t=1"}


def test_meili_settings_do_not_search_ids():
    assert set(build.MEILI_SETTINGS["searchableAttributes"]) == {"text", "text_ascii"}
    assert "ep_key" in build.MEILI_SETTINGS["filterableAttributes"]
```

- [ ] **Step 2: Run to verify failure** — `uv run --no-sync pytest tests/test_build.py -q` → `ModuleNotFoundError: vadibook.build`.

- [ ] **Step 3: Implement `build.py`**

```python
"""Stage 6 (Faz 2): utterances → canonical SQLite + Meilisearch documents."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from vadibook import state
from vadibook.models import Episode, Utterance
from vadibook.paths import data_root, utterances_path

MEILI_INDEX = "utterances"
MEILI_SETTINGS: dict = {
    "searchableAttributes": ["text", "text_ascii"],
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
    part = ep.parts[part_no - 1]
    return f"https://youtu.be/{part.yt_id}?t={int(start - part.offset_sec)}"


def _part_no(u: Utterance) -> int:
    return int(u.speaker.split(":", 1)[0][1:])  # "p2:SPEAKER_03" -> 2


def build_sqlite(episodes: list[Episode]) -> dict:
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
                rows.append((f"{ep.key}:{u.idx:06d}", ep.key, u.idx, part, u.start, u.end, u.speaker,
                             u.text, u.text_norm, u.text_ascii, yt_url(ep, part, u.start)))
        with conn:
            conn.execute("delete from utterances where ep_key = ?", (ep.key,))
            conn.execute("insert or replace into episodes values (?,?,?,?,?,?,?)", (
                ep.key, ep.series, ep.no, ep.parts[0].title, ep.parts[0].yt_id,
                sum(p.duration_sec or 0 for p in ep.parts), json.dumps([p.model_dump() for p in ep.parts], ensure_ascii=False)))
            conn.executemany("insert into utterances values (?,?,?,?,?,?,?,?,?,?,?)", rows)
        n_eps += 1
        n_utts += len(rows)
    conn.close()
    return {"episodes": n_eps, "utterances": n_utts}


def meili_docs(conn: sqlite3.Connection) -> Iterator[dict]:
    q = ("select u.id, e.series, e.no, u.ep_key, u.part, u.start, u.end, u.speaker, u.text, u.text_ascii, u.yt_url "
         "from utterances u join episodes e on e.key = u.ep_key order by u.ep_key, u.idx")
    for r in conn.execute(q):
        yield {"id": r[0], "series": r[1], "ep": r[2], "ep_key": r[3], "part": r[4], "start": r[5], "end": r[6],
               "speaker": r[7], "text": r[8], "text_ascii": r[9], "yt_url": r[10]}


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
```

- [ ] **Step 4: Add `build` command to `cli.py`** (imports `build as build_mod`, `sqlite3`):

```python
@app.command()
def build(
    push: bool = typer.Option(False, "--push", help="Meilisearch'e de gönder"),
    meili_url: str = typer.Option("http://localhost:7700", "--meili-url", envvar="MEILI_URL"),
    meili_key: str = typer.Option("", "--meili-key", envvar="MEILI_MASTER_KEY"),
) -> None:
    """align'ı bitmiş bölümleri SQLite'a yazar; --push ile Meilisearch indeksini günceller."""
    episodes = catalog_mod.load_episodes()
    stats = build_mod.build_sqlite(episodes)
    console.print(f"[green]sqlite[/] {stats['episodes']} bölüm, {stats['utterances']} utterance → {build_mod.sqlite_path()}")
    if push:
        conn = sqlite3.connect(build_mod.sqlite_path())
        n = build_mod.push_meili(meili_url, meili_key, build_mod.meili_docs(conn))
        console.print(f"[green]meilisearch[/] {n} doküman gönderildi → {meili_url}/indexes/{build_mod.MEILI_INDEX}")
```

- [ ] **Step 5: Tests + lint green** — `uv pip install meilisearch && uv add --no-sync meilisearch && uv run --no-sync pytest -q && uv run --no-sync ruff check vadibook tests`
- [ ] **Step 6: Commit** — `git commit -m "feat(pipeline): build stage — SQLite + Meilisearch documents"`

---

### Task 2: Meilisearch locally (Docker Compose)

**Files:** Create `deploy/docker-compose.yml`, `deploy/.env.example`, `deploy/README.md`.

- [ ] **Step 1: Compose file**

```yaml
services:
  meilisearch:
    image: getmeili/meilisearch:v1.15
    environment:
      MEILI_MASTER_KEY: ${MEILI_MASTER_KEY}
      MEILI_ENV: ${MEILI_ENV:-development}
      MEILI_NO_ANALYTICS: "true"
    ports:
      - "127.0.0.1:7700:7700"
    volumes:
      - meili_data:/meili_data
    restart: unless-stopped
volumes:
  meili_data:
```

`deploy/.env.example`: `MEILI_MASTER_KEY=change-me-32-chars-min`. Local `.env` (gitignored) gets a generated key.

- [ ] **Step 2: Start + push** — `docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d` then `uv run --no-sync vadibook build --push --meili-key $KEY`.
  Expected: `sqlite N bölüm …`, `meilisearch M doküman gönderildi`.
- [ ] **Step 3: Verify a search returns a crop only** — `curl -H "Authorization: Bearer $KEY" -X POST localhost:7700/indexes/utterances/search -d '{"q":"kasifoglu","attributesToRetrieve":["id","ep"],"attributesToCrop":["text"],"cropLength":12}'` → hits contain `id`, `ep`, `_formatted.text` and **no** raw `text`.
- [ ] **Step 4: Create a search-only API key** for the web app (`POST /keys` with `actions: ["search"]`, `indexes: ["utterances"]`), store in `web/.env.local`.
- [ ] **Step 5: Commit** deploy files.

---

### Task 3: Next.js scaffold + data libs

**Files:** `web/` (create-next-app), `web/.env.example`, `web/src/lib/db.ts`, `web/src/lib/search.ts`, `web/src/lib/format.ts`. Tests: `web/src/lib/format.test.ts` (vitest).

**Interfaces:**
- `format.fmtTime(sec: number): string` → `"1:23:45"` / `"23:45"`; `format.speakerLabel(raw: string): string` → `"p1:SPEAKER_07"` → `"Konuşmacı 7"`; `format.seriesName(s: "kv"|"pusu"): string` → `"Kurtlar Vadisi"` / `"Kurtlar Vadisi Pusu"`; `format.episodeHref(series, no)`.
- `db.getEpisode(series, no): EpisodeRow | null` (`{key, series, no, title, yt_id, duration_sec, parts: Part[]}`); `db.listEpisodes(): EpisodeRow[]`; `db.episodeStats(key): {utterances, speakers, spokenSec}`; `db.speakerTimeline(key): {speaker, start, end}[]` (no text); `db.corpusStats(): {episodes, utterances, hours}`.
- `search.search({q, series?, ep?, page?}): Promise<{hits: Hit[], total, page, pages, ms}>` where `Hit = {id, series, ep, start, end, speaker, ytUrl, snippet}` (`snippet` = `_formatted.text` with `<mark>`).

- [ ] **Step 1:** `pnpm create next-app@latest web --yes --use-pnpm` (verify it produced TS + Tailwind + `src/app`); `pnpm add meilisearch better-sqlite3 && pnpm add -D @types/better-sqlite3 vitest`.
- [ ] **Step 2:** write `format.test.ts` (fmtTime 3661 → "1:01:01", 83 → "1:23"; speakerLabel; seriesName) → run `pnpm vitest run` → red → implement `format.ts` → green.
- [ ] **Step 3:** implement `db.ts` (better-sqlite3, readonly, path from `VADIBOOK_SQLITE` env, default `../data/private/vadibook.sqlite`; `parts` JSON-parsed) and `search.ts` (Meilisearch client with `MEILI_HOST`/`MEILI_SEARCH_KEY`; `attributesToRetrieve: ["id","series","ep","start","end","speaker","yt_url"]`, `attributesToCrop: ["text"]`, `cropLength: 25`, `attributesToHighlight: ["text"]`, `highlightPreTag: "<mark>"`, `filter` built from series/ep, `hitsPerPage: 20`, `page`).
- [ ] **Step 4:** Commit.

---

### Task 4: `/api/search` + `/ara` results page + SearchBox

**Files:** `web/src/app/api/search/route.ts`, `web/src/app/ara/page.tsx`, `web/src/components/SearchBox.tsx`, `web/src/components/ResultCard.tsx`.

- [ ] **Step 1:** route handler: validate `q` (1–200 chars), `series` ∈ {kv,pusu}, `ep` int, `page` int ≥1; call `search()`; respond JSON with `Cache-Control: public, s-maxage=3600, stale-while-revalidate=86400`. Error → 400 JSON `{error}`.
- [ ] **Step 2:** `/ara` server component: reads `await searchParams`, calls `search()` directly, renders `SearchBox` (prefilled), series filter chips (Tümü / KV / Pusu), result list of `ResultCard`, empty state ("Sonuç yok — şapkasız da dene: kasifoglu"), pagination links (`?q=&page=`).
- [ ] **Step 3:** `ResultCard`: snippet rendered via `dangerouslySetInnerHTML` **after** escaping everything except our own `<mark>` (Meilisearch escapes nothing; implement `renderSnippet(s)` that HTML-escapes then re-enables `&lt;mark&gt;`); meta line: series badge · "N. Bölüm" (link to episode page) · `fmtTime(start)` · speaker label; primary action "YouTube'da o anı izle" (`target=_blank rel=noopener`).
- [ ] **Step 4:** `SearchBox` client component: form → `router.push('/ara?q=...')`, keeps series param; Enter submits.
- [ ] **Step 5:** manual check: `pnpm dev`, open `/ara?q=kasifoglu` and `/ara?q=Kaşifoğlu` → same hits; DevTools Network: response body has `snippet` only, no `text`. Commit.

---

### Task 5: Home + episode page + shell

**Files:** `web/src/app/layout.tsx`, `web/src/app/page.tsx`, `web/src/app/bolum/[series]/[no]/page.tsx`, `web/src/components/SpeakerTimeline.tsx`, `web/src/components/Disclaimer.tsx`.

- [ ] **Step 1:** layout: header with wordmark "vadibook" + compact SearchBox on non-home pages, `Disclaimer` band, footer ("Kaynak: Pana Film'in resmi YouTube yüklemeleri · açık kaynak · GitHub"). Load `frontend-design` skill before styling; pick a deliberate palette (dark, editorial, not default Tailwind blue).
- [ ] **Step 2:** home: hero headline + one-line pitch, big SearchBox, `corpusStats()` counters ("N bölüm · M konuşma · H saat"), example query chips (Kaşifoğlu, İskender Büyük, Tapınakçılar, derin devlet, Ömer Baba), "Son eklenen bölümler" list (from `listEpisodes()` limited 12, linking to episode pages).
- [ ] **Step 3:** episode page: `await params` → `getEpisode()` or `notFound()`; title "Kurtlar Vadisi Pusu — 17. Bölüm"; official embed `https://www.youtube.com/embed/{yt_id}`; stats row; `SpeakerTimeline` (SVG: one lane per speaker sorted by spoken time, rectangles at `start..end` scaled to `duration_sec`; hovering shows time only); "Bu bölümde ara" SearchBox with `ep` filter → `/ara?q=&series=&ep=`; prev/next episode links. No transcript.
- [ ] **Step 4:** `generateMetadata` for episode + search pages (title, description); `robots` allow all except `/api`.
- [ ] **Step 5:** `pnpm build` passes (type-check + lint). Commit.

---

### Task 6: Docs, deploy wiring, handoff

- [ ] **Step 1:** add `web` service to `deploy/docker-compose.yml` (Next standalone image built from `web/Dockerfile`, env `MEILI_HOST=http://meilisearch:7700`, mounts SQLite read-only) — documented, not run locally.
- [ ] **Step 2:** `README.md` (repo root): what it is, legal note, how to run locally (pipeline → `build --push` → `pnpm dev`).
- [ ] **Step 3:** todox: task #302 handoff; commit.

## Self-review

- **Spec coverage:** §8 build (SQLite tables subset: `episodes`, `utterances`; `speakers/scenes/relations` arrive with Faz 3-4) → Task 1; Meilisearch crop-only → Tasks 1-4; `/`, `/ara`, `/bolum` → Tasks 4-5; `/api/search` proxy + cache → Task 4; disclaimer → Task 5; docker-compose → Tasks 2, 6. Not in this plan (by design): `/karakter`, `/grafik`, `/dosya`, OG cards (Faz 4-5).
- **Type consistency:** `yt_url` column name (snake) in SQLite/Meili; `ytUrl` (camel) only in the TS `Hit` type mapped in `search.ts`. `speaker` raw format `p{n}:SPEAKER_xx` everywhere; label conversion only in `format.speakerLabel`. `id` = `"{ep_key}:{idx:06d}"`.
- **Placeholders:** none; UI copy is specified inline.
