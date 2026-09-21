# vadibook Pipeline Core (Faz 0 + Faz 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A resumable Python CLI (`vadibook`) that turns every Kurtlar Vadisi episode on the official YouTube playlists into speaker-labelled, word-timed utterances under `data/private/`, and a completed one-episode spike that fixes the ASR/diarization parameters.

**Architecture:** One `vadibook` package with one module per stage (`catalog → fetch → asr → diarize → align`), each an idempotent function keyed by episode; a tiny `state.py` records which stages finished per episode so `vadibook run --all` can be interrupted and resumed. Pure logic (title parsing, Turkish normalisation, speaker assignment, hallucination filtering) lives in functions with no I/O and is unit-tested; GPU/network code is exercised by the spike task.

**Tech Stack:** Python 3.12 via uv · typer · pydantic v2 · yt-dlp · faster-whisper (CTranslate2, CUDA) · pyannote.audio 4.x (`speaker-diarization-community-1`) · torch cu128 · soundfile · ffmpeg (already installed) · pytest.

**Spec:** `docs/superpowers/specs/2026-09-21-vadibook-design.md` (sections "Pipeline aşamaları" 1–5, "Fazlar" Faz 0–1, "Riskler").

## Global Constraints

- Python pinned to `>=3.12,<3.13` (spec: "Python 3.14: ML wheel'leri yok → uv ile 3.12").
- Everything under `data/private/` is gitignored and never leaves the machine; audio is never redistributed (spec "Telif", "YouTube ToS").
- Only the two official playlists are sources: KV `PLOFoevjhe1HU-FncKpm_OTiSWdTbA7nfh`, Pusu `PLOFoevjhe1HX4HquOBEASUtK_DTfqJSMX`.
- Episode identifiers: id `"{series}/{no}"` (e.g. `pusu/17`) for humans/CLI; key `"{series}-{no:03d}"` (e.g. `pusu-017`) for filenames. `series ∈ {"kv", "pusu"}`.
- Every stage is idempotent per episode and skips work already recorded in `data/private/state/{key}.json` unless `--force`.
- Multi-part uploads ("1. Kısım", "2. Kısım") are modelled as `parts[]` with `offset_sec`; utterance times are episode-global.
- All JSON written with `ensure_ascii=False`, UTF-8.
- Commit messages in English; code comments English; CLI help text Turkish.
- Secrets (`HF_TOKEN`) only via `pipeline/.env` (gitignored); `pipeline/.env.example` documents them.

---

## File Structure

```
pipeline/
  pyproject.toml            uv project; deps; [project.scripts] vadibook = "vadibook.cli:app"
  .python-version           3.12
  .env.example              HF_TOKEN=
  README.md                 usage (written in Task 9)
  vadibook/
    __init__.py
    paths.py                data root (env VADIBOOK_DATA or <repo>/data), per-stage file paths
    models.py               pydantic models: EpisodePart, Episode, Word, AsrSegment, AsrResult, DiarTurn, DiarResult, Utterance
    textnorm.py             normalize_tr(), to_ascii()
    state.py                load/save/is_done/mark_done/record_error per episode
    catalog.py              parse_title(), fetch_playlist(), build_catalog(), gaps(), load/save/find episodes
    fetch.py                download_part(), probe_duration()
    asr.py                  filter_segments() [pure], transcribe() [GPU]
    diarize.py              load_waveform(), diarize() [GPU]
    align.py                words_from_asr(), speaker_at(), assign_speakers(), build_utterances() [pure]
    cli.py                  typer app: catalog | fetch | asr | diarize | align | run | status
  tests/
    conftest.py             data_root fixture (VADIBOOK_DATA → tmp_path)
    test_paths.py test_textnorm.py test_state.py test_catalog.py test_fetch.py
    test_asr.py test_diarize.py test_align.py test_cli.py
docs/superpowers/notes/2026-09-spike-findings.md   (written in Task 10)
```

---

### Task 1: Project scaffold + `paths.py`

**Files:**
- Create: `pipeline/pyproject.toml`, `pipeline/.python-version`, `pipeline/.env.example`, `pipeline/vadibook/__init__.py`, `pipeline/vadibook/paths.py`
- Test: `pipeline/tests/conftest.py`, `pipeline/tests/test_paths.py`

**Interfaces:**
- Produces: `paths.REPO_ROOT: Path`, `paths.data_root() -> Path`, `paths.public_dir() -> Path`, `paths.private_dir(sub: str) -> Path` (creates dir), `paths.episodes_file() -> Path`, `paths.audio_path(key, part) -> Path` (`.opus`), `paths.subs_path(key, part) -> Path` (`.tr.vtt`), `paths.asr_path(key, part) -> Path`, `paths.diar_path(key, part) -> Path`, `paths.utterances_path(key) -> Path`, `paths.state_path(key) -> Path`.

- [ ] **Step 1: Create the uv project files**

`pipeline/pyproject.toml`:

```toml
[project]
name = "vadibook"
version = "0.1.0"
description = "Kurtlar Vadisi transcript + knowledge-graph pipeline"
requires-python = ">=3.12,<3.13"
dependencies = [
  "typer>=0.15",
  "pydantic>=2.9",
  "rich>=13.9",
  "python-dotenv>=1.0",
  "yt-dlp>=2025.1.1",
  "faster-whisper>=1.1",
  "pyannote-audio>=4.0",
  "torch>=2.8",
  "torchaudio>=2.8",
  "soundfile>=0.13",
  "numpy>=1.26",
]

[project.scripts]
vadibook = "vadibook.cli:app"

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.8"]

[tool.uv.sources]
torch = [{ index = "pytorch-cu128", marker = "sys_platform == 'linux' or sys_platform == 'win32'" }]
torchaudio = [{ index = "pytorch-cu128", marker = "sys_platform == 'linux' or sys_platform == 'win32'" }]

[[tool.uv.index]]
name = "pytorch-cu128"
url = "https://download.pytorch.org/whl/cu128"
explicit = true

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["vadibook"]
```

`pipeline/.python-version`:

```
3.12
```

`pipeline/.env.example`:

```
# Hugging Face token. Accept the model terms first:
#   https://huggingface.co/pyannote/speaker-diarization-community-1
HF_TOKEN=
# Optional: move all pipeline data elsewhere (default: <repo>/data)
# VADIBOOK_DATA=D:\vadibook-data
```

`pipeline/vadibook/__init__.py`:

```python
"""vadibook pipeline: Kurtlar Vadisi episodes → speaker-labelled utterances."""
```

- [ ] **Step 2: Write the failing paths test**

`pipeline/tests/conftest.py`:

```python
from pathlib import Path

import pytest


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every path helper at an empty temp dir for the duration of a test."""
    monkeypatch.setenv("VADIBOOK_DATA", str(tmp_path))
    return tmp_path
```

`pipeline/tests/test_paths.py`:

```python
from pathlib import Path

from vadibook import paths


def test_data_root_honours_env(data_root: Path):
    assert paths.data_root() == data_root


def test_private_dir_is_created_under_private(data_root: Path):
    d = paths.private_dir("audio")
    assert d == data_root / "private" / "audio"
    assert d.is_dir()


def test_stage_paths(data_root: Path):
    assert paths.audio_path("pusu-017", 1) == data_root / "private" / "audio" / "pusu-017.p1.opus"
    assert paths.subs_path("pusu-017", 1) == data_root / "private" / "audio" / "pusu-017.p1.tr.vtt"
    assert paths.asr_path("pusu-017", 2) == data_root / "private" / "asr" / "pusu-017.p2.json"
    assert paths.diar_path("kv-001", 1) == data_root / "private" / "diar" / "kv-001.p1.json"
    assert paths.utterances_path("kv-001") == data_root / "private" / "utterances" / "kv-001.jsonl"
    assert paths.state_path("kv-001") == data_root / "private" / "state" / "kv-001.json"
    assert paths.episodes_file() == data_root / "public" / "episodes.json"


def test_repo_root_contains_pipeline_dir():
    assert (paths.REPO_ROOT / "pipeline").is_dir()
```

- [ ] **Step 3: Install and run the test to verify it fails**

Run (from `pipeline/`): `uv python install 3.12 && uv sync --group dev && uv run pytest tests/test_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vadibook.paths'` (the `uv sync` itself may take several minutes: torch cu128 is ~2.5 GB).

- [ ] **Step 4: Implement `paths.py`**

`pipeline/vadibook/paths.py`:

```python
"""Filesystem layout. Everything under private/ is gitignored and never leaves this machine."""

from __future__ import annotations

import os
from pathlib import Path

# pipeline/vadibook/paths.py -> parents[0]=vadibook, [1]=pipeline, [2]=repo root
REPO_ROOT = Path(__file__).resolve().parents[2]


def data_root() -> Path:
    return Path(os.environ.get("VADIBOOK_DATA", REPO_ROOT / "data"))


def public_dir() -> Path:
    d = data_root() / "public"
    d.mkdir(parents=True, exist_ok=True)
    return d


def private_dir(sub: str) -> Path:
    d = data_root() / "private" / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def episodes_file() -> Path:
    return public_dir() / "episodes.json"


def audio_path(key: str, part: int) -> Path:
    return private_dir("audio") / f"{key}.p{part}.opus"


def subs_path(key: str, part: int) -> Path:
    return private_dir("audio") / f"{key}.p{part}.tr.vtt"


def asr_path(key: str, part: int) -> Path:
    return private_dir("asr") / f"{key}.p{part}.json"


def diar_path(key: str, part: int) -> Path:
    return private_dir("diar") / f"{key}.p{part}.json"


def utterances_path(key: str) -> Path:
    return private_dir("utterances") / f"{key}.jsonl"


def state_path(key: str) -> Path:
    return private_dir("state") / f"{key}.json"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_paths.py -v`
Expected: 4 passed.

- [ ] **Step 6: Verify CUDA is visible to torch**

Run: `uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"`
Expected: `2.8.x+cu128 True NVIDIA GeForce RTX 4070`. If `False`, the cu128 index was not used — check `uv.lock` for `torch` source URL before continuing.

- [ ] **Step 7: Commit**

```bash
git add pipeline/pyproject.toml pipeline/.python-version pipeline/.env.example pipeline/uv.lock pipeline/vadibook/__init__.py pipeline/vadibook/paths.py pipeline/tests/conftest.py pipeline/tests/test_paths.py
git commit -m "feat(pipeline): scaffold uv project and path layout"
```

---

### Task 2: Data models + Turkish text normalisation

**Files:**
- Create: `pipeline/vadibook/models.py`, `pipeline/vadibook/textnorm.py`
- Test: `pipeline/tests/test_textnorm.py`, `pipeline/tests/test_models.py`

**Interfaces:**
- Produces (models): `EpisodePart(yt_id: str, title: str, offset_sec: float = 0.0, duration_sec: float | None = None)`; `Episode(series: Literal["kv","pusu"], no: int, parts: list[EpisodePart])` with properties `.key -> str` (`pusu-017`) and `.id -> str` (`pusu/17`); `Word(word: str, start: float, end: float, probability: float)`; `AsrSegment(start, end, text, avg_logprob, no_speech_prob, compression_ratio, words: list[Word] = [])`; `AsrResult(model: str, audio_duration: float, elapsed: float, segments: list[AsrSegment])`; `DiarTurn(start, end, speaker: str)`; `DiarResult(turns: list[DiarTurn], embeddings: dict[str, list[float]], elapsed: float)`; `Utterance(ep: str, idx: int, start: float, end: float, speaker: str, text: str, text_norm: str, text_ascii: str, words: list[Word])`.
- Produces (textnorm): `normalize_tr(text: str) -> str` (Turkish-aware lowercase, circumflex removed); `to_ascii(text: str) -> str` (normalize_tr + ç/ğ/ı/ö/ş/ü folded).

- [ ] **Step 1: Write the failing textnorm tests**

`pipeline/tests/test_textnorm.py`:

```python
from vadibook.textnorm import normalize_tr, to_ascii


def test_dotted_capital_i_lowercases_to_dotted_i():
    assert normalize_tr("İstanbul") == "istanbul"


def test_dotless_capital_i_lowercases_to_dotless_i():
    assert normalize_tr("ISPARTA") == "ısparta"


def test_circumflex_is_removed():
    assert normalize_tr("Kâşif Kozinoğlu") == "kaşif kozinoğlu"


def test_ascii_fold():
    assert to_ascii("Kaşifoğlu") == "kasifoglu"
    assert to_ascii("Çakır Süleyman Ömer İbrahim") == "cakir suleyman omer ibrahim"


def test_normalize_keeps_punctuation_and_spaces():
    assert normalize_tr("Polat, gel!  ") == "polat, gel!  "
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_textnorm.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'vadibook.textnorm'`.

- [ ] **Step 3: Implement `textnorm.py`**

`pipeline/vadibook/textnorm.py`:

```python
"""Turkish-aware normalisation for search fields.

Python's str.lower() turns "İ" into "i̇" (i + combining dot) and "I" into "i"; both are
wrong for Turkish. We map the two capitals first, then lower the rest.
"""

_TR_CAPITALS = str.maketrans({"I": "ı", "İ": "i"})
_CIRCUMFLEX = str.maketrans({"â": "a", "î": "i", "û": "u"})
_ASCII_FOLD = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u"})


def normalize_tr(text: str) -> str:
    """Lowercase with Turkish i/ı rules and strip circumflexes (kâr -> kar)."""
    return text.translate(_TR_CAPITALS).lower().translate(_CIRCUMFLEX)


def to_ascii(text: str) -> str:
    """normalize_tr + fold Turkish letters to ASCII so 'kasifoglu' matches 'Kaşifoğlu'."""
    return normalize_tr(text).translate(_ASCII_FOLD)
```

- [ ] **Step 4: Run textnorm tests**

Run: `uv run pytest tests/test_textnorm.py -v`
Expected: 5 passed.

- [ ] **Step 5: Write the failing models test**

`pipeline/tests/test_models.py`:

```python
from vadibook.models import Episode, EpisodePart, Utterance, Word


def test_episode_key_and_id():
    ep = Episode(series="pusu", no=17, parts=[EpisodePart(yt_id="abc", title="t")])
    assert ep.key == "pusu-017"
    assert ep.id == "pusu/17"


def test_episode_roundtrips_through_json():
    ep = Episode(series="kv", no=1, parts=[EpisodePart(yt_id="x", title="1. Bölüm", duration_sec=90.5)])
    again = Episode.model_validate_json(ep.model_dump_json())
    assert again == ep


def test_utterance_requires_all_search_fields():
    u = Utterance(
        ep="kv/1", idx=0, start=1.0, end=2.0, speaker="p1:SPEAKER_00",
        text="Merhaba", text_norm="merhaba", text_ascii="merhaba",
        words=[Word(word=" Merhaba", start=1.0, end=2.0, probability=0.9)],
    )
    assert u.words[0].word.strip() == "Merhaba"
```

- [ ] **Step 6: Run to verify failure**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'vadibook.models'`.

- [ ] **Step 7: Implement `models.py`**

`pipeline/vadibook/models.py`:

```python
"""Pydantic models shared by every stage. Times are seconds (float)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Series = Literal["kv", "pusu"]


class EpisodePart(BaseModel):
    """One YouTube video. Most episodes have exactly one part."""

    yt_id: str
    title: str
    offset_sec: float = 0.0  # where this part starts on the episode-global timeline
    duration_sec: float | None = None  # playlist estimate until `fetch` probes the file


class Episode(BaseModel):
    series: Series
    no: int
    parts: list[EpisodePart] = Field(min_length=1)

    @property
    def key(self) -> str:
        """Filesystem-safe id: pusu-017."""
        return f"{self.series}-{self.no:03d}"

    @property
    def id(self) -> str:
        """Human/CLI id: pusu/17."""
        return f"{self.series}/{self.no}"


class Word(BaseModel):
    word: str  # as emitted by whisper, usually with a leading space
    start: float
    end: float
    probability: float


class AsrSegment(BaseModel):
    start: float
    end: float
    text: str
    avg_logprob: float
    no_speech_prob: float
    compression_ratio: float
    words: list[Word] = []


class AsrResult(BaseModel):
    model: str
    audio_duration: float
    elapsed: float
    segments: list[AsrSegment]


class DiarTurn(BaseModel):
    start: float
    end: float
    speaker: str  # local label from pyannote, e.g. SPEAKER_00


class DiarResult(BaseModel):
    turns: list[DiarTurn]
    embeddings: dict[str, list[float]]  # local speaker label -> embedding vector
    elapsed: float


class Utterance(BaseModel):
    ep: str  # episode id, e.g. pusu/17
    idx: int  # 0-based, global across parts
    start: float  # episode-global seconds
    end: float
    speaker: str  # "p{part}:{local label}", e.g. p1:SPEAKER_03
    text: str
    text_norm: str
    text_ascii: str
    words: list[Word]
```

- [ ] **Step 8: Run all tests**

Run: `uv run pytest -v`
Expected: all pass (paths 4 + textnorm 5 + models 3).

- [ ] **Step 9: Commit**

```bash
git add pipeline/vadibook/models.py pipeline/vadibook/textnorm.py pipeline/tests/test_textnorm.py pipeline/tests/test_models.py
git commit -m "feat(pipeline): add data models and Turkish text normalisation"
```

---

### Task 3: Per-episode stage state

**Files:**
- Create: `pipeline/vadibook/state.py`
- Test: `pipeline/tests/test_state.py`

**Interfaces:**
- Consumes: `paths.state_path(key)`.
- Produces: `state.load(key) -> dict`, `state.save(key, st: dict) -> None`, `state.is_done(key, stage) -> bool`, `state.mark_done(key, stage, **meta) -> None`, `state.clear(key, stage) -> None`, `state.record_error(key, stage, message: str) -> None`, `state.stage_meta(key, stage) -> dict | None`.
- State file shape: `{"stages": {"asr": {"done_at": 1726900000.0, "rtf": 0.05, ...}}, "errors": {"diarize": {"at": ..., "message": "..."}}}`.

- [ ] **Step 1: Write the failing tests**

`pipeline/tests/test_state.py`:

```python
from vadibook import state


def test_fresh_episode_has_nothing_done(data_root):
    assert state.is_done("kv-001", "fetch") is False
    assert state.stage_meta("kv-001", "fetch") is None


def test_mark_done_persists_meta(data_root):
    state.mark_done("kv-001", "asr", model="large-v3", rtf=0.05)
    assert state.is_done("kv-001", "asr") is True
    meta = state.stage_meta("kv-001", "asr")
    assert meta["model"] == "large-v3"
    assert meta["rtf"] == 0.05
    assert meta["done_at"] > 0


def test_clear_removes_only_that_stage(data_root):
    state.mark_done("kv-001", "fetch")
    state.mark_done("kv-001", "asr")
    state.clear("kv-001", "asr")
    assert state.is_done("kv-001", "fetch") is True
    assert state.is_done("kv-001", "asr") is False


def test_record_error_keeps_stage_not_done(data_root):
    state.record_error("kv-001", "diarize", "CUDA out of memory")
    assert state.is_done("kv-001", "diarize") is False
    assert state.load("kv-001")["errors"]["diarize"]["message"] == "CUDA out of memory"


def test_state_file_is_utf8_json(data_root):
    state.mark_done("kv-001", "fetch", note="Bölüm")
    raw = (data_root / "private" / "state" / "kv-001.json").read_text(encoding="utf-8")
    assert "Bölüm" in raw  # ensure_ascii=False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'vadibook.state'`.

- [ ] **Step 3: Implement `state.py`**

`pipeline/vadibook/state.py`:

```python
"""Per-episode progress record so long runs can be interrupted and resumed."""

from __future__ import annotations

import json
import time
from typing import Any

from vadibook.paths import state_path


def load(key: str) -> dict[str, Any]:
    p = state_path(key)
    if not p.exists():
        return {"stages": {}, "errors": {}}
    st = json.loads(p.read_text(encoding="utf-8"))
    st.setdefault("stages", {})
    st.setdefault("errors", {})
    return st


def save(key: str, st: dict[str, Any]) -> None:
    state_path(key).write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def is_done(key: str, stage: str) -> bool:
    return stage in load(key)["stages"]


def stage_meta(key: str, stage: str) -> dict[str, Any] | None:
    return load(key)["stages"].get(stage)


def mark_done(key: str, stage: str, **meta: Any) -> None:
    st = load(key)
    st["stages"][stage] = {"done_at": time.time(), **meta}
    st["errors"].pop(stage, None)
    save(key, st)


def clear(key: str, stage: str) -> None:
    st = load(key)
    st["stages"].pop(stage, None)
    save(key, st)


def record_error(key: str, stage: str, message: str) -> None:
    st = load(key)
    st["errors"][stage] = {"at": time.time(), "message": message}
    save(key, st)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_state.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/vadibook/state.py pipeline/tests/test_state.py
git commit -m "feat(pipeline): add resumable per-episode stage state"
```

---

### Task 4: Catalog (playlist → `episodes.json`) + first CLI command

**Files:**
- Create: `pipeline/vadibook/catalog.py`, `pipeline/vadibook/cli.py`
- Test: `pipeline/tests/test_catalog.py`

**Interfaces:**
- Consumes: `models.Episode`, `models.EpisodePart`, `paths.episodes_file()`.
- Produces: `catalog.PLAYLISTS: dict[str, str]` (`{"kv": url, "pusu": url}`); `catalog.parse_title(title: str, default_series: str) -> tuple[str, int, int | None] | None` → `(series, episode_no, part_no)`; `catalog.fetch_playlist(url: str) -> list[dict]` (each `{"id", "title", "duration"}`); `catalog.build_catalog(entries_by_series: dict[str, list[dict]]) -> tuple[list[Episode], list[str]]` (episodes sorted, warnings); `catalog.gaps(episodes, expected: dict[str, int] = EXPECTED) -> list[str]`; `catalog.load_episodes() -> list[Episode]`; `catalog.save_episodes(episodes) -> None`; `catalog.find_episode(episodes, ep_id: str) -> Episode` (raises `KeyError`).
- Produces (cli): typer app `cli.app` with command `catalog`.

- [ ] **Step 1: Write the failing tests**

`pipeline/tests/test_catalog.py`:

```python
import json

import pytest

from vadibook import catalog
from vadibook.models import Episode


@pytest.mark.parametrize(
    "title,default,expected",
    [
        ("Kurtlar Vadisi Pusu 123. Bölüm FULL HD", "pusu", ("pusu", 123, None)),
        ("Kurtlar Vadisi - 80. Bölüm FULL HD", "kv", ("kv", 80, None)),
        ("1.Bölüm - Kurtlar Vadisi | 4K", "kv", ("kv", 1, None)),
        ("Kurtlar Vadisi Pusu 5.Bölüm 2.Kısım", "pusu", ("pusu", 5, 2)),
        ("Kurtlar Vadisi Pusu 300. Bölüm (Final)", "pusu", ("pusu", 300, None)),
        ("Kurtlar Vadisi Pusu 12. Bölüm", "kv", ("pusu", 12, None)),  # title wins over playlist
        ("KURTLAR VADİSİ 7. BÖLÜM", "kv", ("kv", 7, None)),
        ("Kurtlar Vadisi Fragman", "kv", None),
    ],
)
def test_parse_title(title, default, expected):
    assert catalog.parse_title(title, default) == expected


def test_build_catalog_groups_parts_and_computes_offsets():
    entries = {
        "pusu": [
            {"id": "b", "title": "Kurtlar Vadisi Pusu 5. Bölüm 2. Kısım", "duration": 3000},
            {"id": "a", "title": "Kurtlar Vadisi Pusu 5. Bölüm 1. Kısım", "duration": 2500},
            {"id": "c", "title": "Kurtlar Vadisi Pusu 6. Bölüm", "duration": 5400},
        ]
    }
    episodes, warnings = catalog.build_catalog(entries)
    assert warnings == []
    assert [e.id for e in episodes] == ["pusu/5", "pusu/6"]
    ep5 = episodes[0]
    assert [p.yt_id for p in ep5.parts] == ["a", "b"]
    assert ep5.parts[0].offset_sec == 0.0
    assert ep5.parts[1].offset_sec == 2500.0
    assert ep5.parts[1].duration_sec == 3000.0


def test_build_catalog_warns_on_unparsed_and_duplicates():
    entries = {
        "kv": [
            {"id": "x", "title": "Kurtlar Vadisi 3. Bölüm", "duration": 100},
            {"id": "y", "title": "Kurtlar Vadisi 3. Bölüm FULL HD", "duration": 100},
            {"id": "z", "title": "Kurtlar Vadisi Kamera Arkası", "duration": 100},
        ]
    }
    episodes, warnings = catalog.build_catalog(entries)
    assert len(episodes) == 1 and episodes[0].parts[0].yt_id == "x"
    assert any("unparsed" in w and "z" in w for w in warnings)
    assert any("duplicate" in w and "kv/3" in w for w in warnings)


def test_gaps_reports_missing_numbers():
    episodes, _ = catalog.build_catalog(
        {"kv": [{"id": "a", "title": "Kurtlar Vadisi 1. Bölüm", "duration": 1},
                {"id": "b", "title": "Kurtlar Vadisi 3. Bölüm", "duration": 1}]}
    )
    assert catalog.gaps(episodes, expected={"kv": 3, "pusu": 0}) == ["kv/2"]


def test_save_load_find(data_root):
    episodes, _ = catalog.build_catalog(
        {"pusu": [{"id": "a", "title": "Kurtlar Vadisi Pusu 17. Bölüm", "duration": 10}]}
    )
    catalog.save_episodes(episodes)
    raw = json.loads((data_root / "public" / "episodes.json").read_text(encoding="utf-8"))
    assert raw[0]["series"] == "pusu"
    loaded = catalog.load_episodes()
    assert loaded == episodes
    assert catalog.find_episode(loaded, "pusu/17").key == "pusu-017"
    with pytest.raises(KeyError):
        catalog.find_episode(loaded, "pusu/18")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_catalog.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'vadibook.catalog'`.

- [ ] **Step 3: Implement `catalog.py`**

`pipeline/vadibook/catalog.py`:

```python
"""Stage 1: turn the two official playlists into data/public/episodes.json."""

from __future__ import annotations

import json
import re

from vadibook.models import Episode, EpisodePart
from vadibook.paths import episodes_file

PLAYLISTS: dict[str, str] = {
    "kv": "https://www.youtube.com/playlist?list=PLOFoevjhe1HU-FncKpm_OTiSWdTbA7nfh",
    "pusu": "https://www.youtube.com/playlist?list=PLOFoevjhe1HX4HquOBEASUtK_DTfqJSMX",
}
EXPECTED: dict[str, int] = {"kv": 97, "pusu": 300}

# "123. Bölüm", "123.Bölüm", "123 Bölüm", case/diacritic-insensitive
_EPISODE_RE = re.compile(r"(?<!\d)(\d{1,3})\s*\.?\s*B[öÖo]L[üÜu]M", re.IGNORECASE)
# "2. Kısım"
_PART_RE = re.compile(r"(?<!\d)(\d{1,2})\s*\.?\s*K[ıİi]S[ıİi]M", re.IGNORECASE)
_PUSU_RE = re.compile(r"pusu", re.IGNORECASE)


def parse_title(title: str, default_series: str) -> tuple[str, int, int | None] | None:
    """Return (series, episode_no, part_no) or None when the title is not an episode."""
    m = _EPISODE_RE.search(title)
    if not m:
        return None
    series = "pusu" if _PUSU_RE.search(title) else default_series
    pm = _PART_RE.search(title)
    return series, int(m.group(1)), int(pm.group(1)) if pm else None


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


def build_catalog(entries_by_series: dict[str, list[dict]]) -> tuple[list[Episode], list[str]]:
    """Group flat entries into episodes (with ordered parts). Returns (episodes, warnings)."""
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
            warnings.append(f"duplicate: {series}/{no} has {len(items)} videos without part numbers ({ids}); keeping first")
            items = items[:1]
        items.sort(key=lambda it: it[0] or 1)
        parts: list[EpisodePart] = []
        offset = 0.0
        for _, e in items:
            dur = float(e["duration"]) if e.get("duration") else None
            parts.append(EpisodePart(yt_id=e["id"], title=e["title"], offset_sec=offset, duration_sec=dur))
            offset += dur or 0.0
        episodes.append(Episode(series=series, no=no, parts=parts))  # type: ignore[arg-type]
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_catalog.py -v`
Expected: 12 passed (8 parametrised + 4).

- [ ] **Step 5: Create `cli.py` with the `catalog` command**

`pipeline/vadibook/cli.py`:

```python
"""vadibook CLI. Each stage command is idempotent per episode; see `vadibook run`."""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console

from vadibook import catalog as catalog_mod
from vadibook.paths import REPO_ROOT

load_dotenv(REPO_ROOT / "pipeline" / ".env")

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Kurtlar Vadisi transkript pipeline'ı")
console = Console()


@app.command()
def catalog() -> None:
    """İki resmi playlist'i tarayıp data/public/episodes.json üretir; eksik/çift bölümleri raporlar."""
    entries = {series: catalog_mod.fetch_playlist(url) for series, url in catalog_mod.PLAYLISTS.items()}
    for series, items in entries.items():
        console.print(f"[bold]{series}[/]: {len(items)} video")
    episodes, warnings = catalog_mod.build_catalog(entries)
    catalog_mod.save_episodes(episodes)
    for w in warnings:
        console.print(f"[yellow]uyarı[/] {w}")
    missing = catalog_mod.gaps(episodes)
    if missing:
        console.print(f"[red]eksik {len(missing)} bölüm:[/] {', '.join(missing)}")
    console.print(f"[green]{len(episodes)} bölüm yazıldı[/] → {catalog_mod.episodes_file()}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 6: Smoke-run the real catalog (network)**

Run: `uv run vadibook catalog`
Expected: prints `kv: N video`, `pusu: M video`, warnings for non-episode videos (trailers etc.), a gaps line, and `... bölüm yazıldı`. Open `data/public/episodes.json` and eyeball 3 entries. If the gaps list is long (>10), the title regex needs another pattern — add the failing title to the `test_parse_title` parametrisation, fix the regex, re-run. Do **not** hand-edit `episodes.json` yet; the file is regenerated by this command.

- [ ] **Step 7: Commit**

```bash
git add pipeline/vadibook/catalog.py pipeline/vadibook/cli.py pipeline/tests/test_catalog.py data/public/episodes.json
git commit -m "feat(pipeline): catalog official playlists into episodes.json"
```

---

### Task 5: Fetch (audio download + duration probe)

**Files:**
- Create: `pipeline/vadibook/fetch.py`
- Modify: `pipeline/vadibook/cli.py` (add `fetch` command + shared episode selection)
- Test: `pipeline/tests/test_fetch.py`, `pipeline/tests/test_cli.py`

**Interfaces:**
- Consumes: `paths.audio_path`, `paths.subs_path`, `models.Episode`, `state.*`, `catalog.load_episodes/save_episodes/find_episode`.
- Produces: `fetch.download_part(yt_id: str, key: str, part_no: int, *, sleep: float = 5.0) -> Path` (returns existing file without downloading); `fetch.probe_duration(path: Path) -> float` (ffprobe); `fetch.fetch_episode(ep: Episode, *, sleep: float = 5.0) -> Episode` (downloads all parts, returns a copy with measured `duration_sec`/`offset_sec`).
- Produces (cli): `cli.select_episodes(episodes: list[Episode], ep: list[str], all_: bool, series: str | None) -> list[Episode]`; command `fetch`.

- [ ] **Step 1: Write the failing tests**

`pipeline/tests/test_fetch.py`:

```python
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
```

`pipeline/tests/test_cli.py`:

```python
import pytest
import typer

from vadibook.cli import select_episodes
from vadibook.models import Episode, EpisodePart


def _eps():
    return [
        Episode(series="kv", no=1, parts=[EpisodePart(yt_id="a", title="")]),
        Episode(series="pusu", no=1, parts=[EpisodePart(yt_id="b", title="")]),
        Episode(series="pusu", no=2, parts=[EpisodePart(yt_id="c", title="")]),
    ]


def test_select_by_id():
    assert [e.id for e in select_episodes(_eps(), ["pusu/2", "kv/1"], False, None)] == ["pusu/2", "kv/1"]


def test_select_all_and_series_filter():
    assert len(select_episodes(_eps(), [], True, None)) == 3
    assert [e.id for e in select_episodes(_eps(), [], False, "pusu")] == ["pusu/1", "pusu/2"]


def test_select_nothing_is_an_error():
    with pytest.raises(typer.BadParameter):
        select_episodes(_eps(), [], False, None)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_fetch.py tests/test_cli.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'vadibook.fetch'` and `ImportError: cannot import name 'select_episodes'`.

- [ ] **Step 3: Implement `fetch.py`**

`pipeline/vadibook/fetch.py`:

```python
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
```

- [ ] **Step 4: Add episode selection + `fetch` command to `cli.py`**

Replace the whole file:

```python
"""vadibook CLI. Each stage command is idempotent per episode; see `vadibook run`."""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console

from vadibook import catalog as catalog_mod
from vadibook import fetch as fetch_mod
from vadibook import state
from vadibook.models import Episode
from vadibook.paths import REPO_ROOT

load_dotenv(REPO_ROOT / "pipeline" / ".env")

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Kurtlar Vadisi transkript pipeline'ı")
console = Console()

EpOpt = typer.Option([], "--ep", help="Bölüm id'si, tekrarlanabilir: --ep pusu/17 --ep kv/3")
AllOpt = typer.Option(False, "--all", help="Katalogdaki tüm bölümler")
SeriesOpt = typer.Option(None, "--series", help="Sadece bu seri: kv | pusu")
ForceOpt = typer.Option(False, "--force", help="Bitmiş aşamayı yeniden çalıştır")


def select_episodes(episodes: list[Episode], ep: list[str], all_: bool, series: str | None) -> list[Episode]:
    if ep:
        selected = [catalog_mod.find_episode(episodes, e) for e in ep]
    elif all_ or series:
        selected = list(episodes)
    else:
        raise typer.BadParameter("--ep SERİ/NO (tekrarlanabilir), --series veya --all ver")
    if series:
        selected = [e for e in selected if e.series == series]
    return selected


def _replace_episode(episodes: list[Episode], updated: Episode) -> list[Episode]:
    return [updated if e.id == updated.id else e for e in episodes]


@app.command()
def catalog() -> None:
    """İki resmi playlist'i tarayıp data/public/episodes.json üretir; eksik/çift bölümleri raporlar."""
    entries = {series: catalog_mod.fetch_playlist(url) for series, url in catalog_mod.PLAYLISTS.items()}
    for series, items in entries.items():
        console.print(f"[bold]{series}[/]: {len(items)} video")
    episodes, warnings = catalog_mod.build_catalog(entries)
    catalog_mod.save_episodes(episodes)
    for w in warnings:
        console.print(f"[yellow]uyarı[/] {w}")
    missing = catalog_mod.gaps(episodes)
    if missing:
        console.print(f"[red]eksik {len(missing)} bölüm:[/] {', '.join(missing)}")
    console.print(f"[green]{len(episodes)} bölüm yazıldı[/] → {catalog_mod.episodes_file()}")


@app.command()
def fetch(
    ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt,
    sleep: float = typer.Option(5.0, help="İndirmeler arası bekleme (sn), YouTube throttling'e karşı"),
) -> None:
    """Sesi (yalnız ses) ve otomatik TR altyazıyı indirir; parça sürelerini ölçüp episodes.json'ı günceller."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        if state.is_done(e.key, "fetch") and not force:
            console.print(f"[dim]{e.id} fetch atlandı (bitmiş)[/]")
            continue
        try:
            updated = fetch_mod.fetch_episode(e, sleep=sleep)
        except Exception as exc:  # noqa: BLE001 — keep the batch going, record the failure
            state.record_error(e.key, "fetch", str(exc))
            console.print(f"[red]{e.id} fetch hata:[/] {exc}")
            continue
        episodes = _replace_episode(episodes, updated)
        catalog_mod.save_episodes(episodes)
        total = sum(p.duration_sec or 0 for p in updated.parts)
        state.mark_done(e.key, "fetch", parts=len(updated.parts), duration_sec=total)
        console.print(f"[green]{e.id}[/] {len(updated.parts)} parça, {total/60:.1f} dk")


if __name__ == "__main__":
    app()
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_fetch.py tests/test_cli.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/vadibook/fetch.py pipeline/vadibook/cli.py pipeline/tests/test_fetch.py pipeline/tests/test_cli.py
git commit -m "feat(pipeline): fetch audio + auto subs with measured part durations"
```

---

### Task 6: ASR (faster-whisper) with hallucination filter

**Files:**
- Create: `pipeline/vadibook/asr.py`
- Modify: `pipeline/vadibook/cli.py` (add `asr` command)
- Test: `pipeline/tests/test_asr.py`

**Interfaces:**
- Consumes: `models.AsrSegment/AsrResult/Word`, `textnorm.normalize_tr`, `paths.audio_path/asr_path`, `state.*`.
- Produces: `asr.HALLUCINATION_BLOCKLIST: tuple[str, ...]`; `asr.INITIAL_PROMPT: str`; `asr.filter_segments(segments: list[AsrSegment], *, no_speech_max: float = 0.6, compression_max: float = 2.4, blocklist=HALLUCINATION_BLOCKLIST) -> list[AsrSegment]`; `asr.transcribe(audio: Path, *, model_name: str = "large-v3", batch_size: int = 16) -> AsrResult`.
- Output file `asr/{key}.p{n}.json` = `AsrResult.model_dump_json()`.

- [ ] **Step 1: Write the failing filter tests**

`pipeline/tests/test_asr.py`:

```python
from vadibook.asr import filter_segments
from vadibook.models import AsrSegment


def seg(text, *, no_speech=0.1, comp=1.2):
    return AsrSegment(start=0, end=1, text=text, avg_logprob=-0.3, no_speech_prob=no_speech, compression_ratio=comp)


def test_keeps_ordinary_speech():
    out = filter_segments([seg(" Polat, gel buraya.")])
    assert [s.text for s in out] == [" Polat, gel buraya."]


def test_drops_high_no_speech_prob():
    assert filter_segments([seg("...", no_speech=0.9)]) == []


def test_drops_repetitive_output():
    assert filter_segments([seg("evet evet evet evet evet", comp=3.1)]) == []


def test_drops_known_turkish_whisper_hallucinations_case_insensitively():
    assert filter_segments([seg(" Altyazı M.K."), seg("ALTYAZI M.K"), seg(" İzlediğiniz için teşekkürler.")]) == []


def test_drops_empty_text():
    assert filter_segments([seg("   ")]) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_asr.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'vadibook.asr'`.

- [ ] **Step 3: Implement `asr.py`**

`pipeline/vadibook/asr.py`:

```python
"""Stage 3: faster-whisper transcription with word timestamps.

Windows note: ctranslate2 needs cuBLAS/cuDNN DLLs. Importing torch first puts the ones shipped
in torch/lib on the loader path, which is why `import torch` sits above `faster_whisper`.
"""

from __future__ import annotations

import time
from pathlib import Path

import torch  # noqa: F401  (see module docstring)

from vadibook.models import AsrResult, AsrSegment, Word
from vadibook.textnorm import normalize_tr

# Whisper's well-known Turkish hallucinations on music/silence (subtitle credits, outros).
HALLUCINATION_BLOCKLIST: tuple[str, ...] = (
    "altyazı m.k",
    "altyazı: m.k",
    "izlediğiniz için teşekkür",
    "abone olmayı unutmayın",
)

# Proper names bias the decoder toward the show's vocabulary (spec "Kalite" risk).
INITIAL_PROMPT = (
    "Kurtlar Vadisi Pusu. Polat Alemdar, Memati Baş, Abdülhey Çoban, Süleyman Çakır, Laz Ziya, "
    "İskender Büyük, Kaşifoğlu, Aron Feller, Ömer Baba, Elif Eylül, Tapınakçılar, KGT."
)

_pipelines: dict[str, object] = {}


def get_pipeline(model_name: str):
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    if model_name not in _pipelines:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute = "float16" if device == "cuda" else "int8"
        _pipelines[model_name] = BatchedInferencePipeline(model=WhisperModel(model_name, device=device, compute_type=compute))
    return _pipelines[model_name]


def filter_segments(
    segments: list[AsrSegment],
    *,
    no_speech_max: float = 0.6,
    compression_max: float = 2.4,
    blocklist: tuple[str, ...] = HALLUCINATION_BLOCKLIST,
) -> list[AsrSegment]:
    kept: list[AsrSegment] = []
    for s in segments:
        text = normalize_tr(s.text).strip()
        if not text:
            continue
        if s.no_speech_prob > no_speech_max or s.compression_ratio > compression_max:
            continue
        if any(b in text for b in blocklist):
            continue
        kept.append(s)
    return kept


def transcribe(audio: Path, *, model_name: str = "large-v3", batch_size: int = 16) -> AsrResult:
    t0 = time.perf_counter()
    segments_iter, info = get_pipeline(model_name).transcribe(
        str(audio),
        language="tr",
        batch_size=batch_size,
        word_timestamps=True,
        vad_filter=True,
        initial_prompt=INITIAL_PROMPT,
    )
    segments = [
        AsrSegment(
            start=s.start, end=s.end, text=s.text,
            avg_logprob=s.avg_logprob, no_speech_prob=s.no_speech_prob, compression_ratio=s.compression_ratio,
            words=[Word(word=w.word, start=w.start, end=w.end, probability=w.probability) for w in (s.words or [])],
        )
        for s in segments_iter  # transcription actually runs while iterating
    ]
    return AsrResult(
        model=model_name,
        audio_duration=float(info.duration),
        elapsed=time.perf_counter() - t0,
        segments=filter_segments(segments),
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_asr.py -v`
Expected: 5 passed.

- [ ] **Step 5: Add the `asr` command to `cli.py`**

Add the import `from vadibook import asr as asr_mod` and `from vadibook.paths import asr_path, audio_path` next to the other imports, then append before `if __name__ == "__main__":`:

```python
@app.command()
def asr(
    ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt,
    model: str = typer.Option("large-v3", help="faster-whisper modeli: large-v3 | large-v3-turbo"),
    batch_size: int = typer.Option(16, help="Batched inference boyutu (VRAM'e göre)"),
) -> None:
    """Sesi faster-whisper ile kelime zamanlı transkript eder → data/private/asr/."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        if state.is_done(e.key, "asr") and not force:
            console.print(f"[dim]{e.id} asr atlandı (bitmiş)[/]")
            continue
        if not state.is_done(e.key, "fetch"):
            console.print(f"[yellow]{e.id} asr atlandı: önce fetch[/]")
            continue
        try:
            total_dur = total_elapsed = 0.0
            for i, _ in enumerate(e.parts, start=1):
                result = asr_mod.transcribe(audio_path(e.key, i), model_name=model, batch_size=batch_size)
                asr_path(e.key, i).write_text(result.model_dump_json(), encoding="utf-8")
                total_dur += result.audio_duration
                total_elapsed += result.elapsed
        except Exception as exc:  # noqa: BLE001
            state.record_error(e.key, "asr", str(exc))
            console.print(f"[red]{e.id} asr hata:[/] {exc}")
            continue
        rtf = total_elapsed / total_dur if total_dur else 0.0
        state.mark_done(e.key, "asr", model=model, rtf=round(rtf, 4), elapsed=round(total_elapsed, 1))
        console.print(f"[green]{e.id}[/] asr {total_elapsed/60:.1f} dk, RTF {rtf:.3f} ({1/rtf if rtf else 0:.0f}× gerçek zaman)")
```

- [ ] **Step 6: Commit**

```bash
git add pipeline/vadibook/asr.py pipeline/vadibook/cli.py pipeline/tests/test_asr.py
git commit -m "feat(pipeline): faster-whisper ASR with Turkish hallucination filter"
```

---

### Task 7: Diarization (pyannote)

**Files:**
- Create: `pipeline/vadibook/diarize.py`
- Modify: `pipeline/vadibook/cli.py` (add `diarize` command)
- Test: `pipeline/tests/test_diarize.py`

**Interfaces:**
- Consumes: `models.DiarTurn/DiarResult`, `paths.audio_path/diar_path`, `state.*`, env `HF_TOKEN`.
- Produces: `diarize.MODEL = "pyannote/speaker-diarization-community-1"`; `diarize.load_waveform(audio: Path) -> dict` (`{"waveform": torch.Tensor[1, N], "sample_rate": 16000}`, decoded by ffmpeg so pyannote's torchcodec path is never needed); `diarize.result_from_output(output) -> tuple[list[DiarTurn], dict[str, list[float]]]` (pure adapter over pyannote's output); `diarize.diarize(audio: Path) -> DiarResult`.
- Output file `diar/{key}.p{n}.json` = `DiarResult.model_dump_json()`.

- [ ] **Step 1: Write the failing tests**

`pipeline/tests/test_diarize.py`:

```python
from types import SimpleNamespace

import numpy as np
import torch

from tests.test_fetch import make_tone
from vadibook import diarize


def test_load_waveform_is_mono_16k(tmp_path):
    wav = make_tone(tmp_path / "t.wav", 1.0)
    out = diarize.load_waveform(wav)
    assert out["sample_rate"] == 16000
    assert isinstance(out["waveform"], torch.Tensor)
    assert out["waveform"].shape[0] == 1
    assert abs(out["waveform"].shape[1] - 16000) < 100


class FakeSegment:
    def __init__(self, start, end):
        self.start, self.end = start, end


class FakeAnnotation:
    def __init__(self, tracks):
        self._tracks = tracks  # list of (start, end, label)

    def itertracks(self, yield_label=False):
        for s, e, lab in self._tracks:
            yield FakeSegment(s, e), "track", lab

    def labels(self):
        return sorted({lab for _, _, lab in self._tracks})


def test_result_from_diarize_output_uses_exclusive_turns_and_embeddings():
    exclusive = FakeAnnotation([(0.0, 1.0, "SPEAKER_00"), (1.0, 2.0, "SPEAKER_01")])
    full = FakeAnnotation([(0.0, 1.2, "SPEAKER_00"), (0.9, 2.0, "SPEAKER_01")])
    output = SimpleNamespace(
        speaker_diarization=full,
        exclusive_speaker_diarization=exclusive,
        speaker_embeddings=np.array([[1.0, 0.0], [0.0, 1.0]]),
    )
    turns, emb = diarize.result_from_output(output)
    assert [(t.start, t.end, t.speaker) for t in turns] == [(0.0, 1.0, "SPEAKER_00"), (1.0, 2.0, "SPEAKER_01")]
    assert emb == {"SPEAKER_00": [1.0, 0.0], "SPEAKER_01": [0.0, 1.0]}


def test_result_from_plain_annotation_has_no_embeddings():
    ann = FakeAnnotation([(0.0, 1.0, "SPEAKER_00")])
    turns, emb = diarize.result_from_output(ann)
    assert len(turns) == 1 and emb == {}
```

Add an empty `pipeline/tests/__init__.py` so `from tests.test_fetch import make_tone` resolves.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_diarize.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'vadibook.diarize'`.

- [ ] **Step 3: Implement `diarize.py`**

`pipeline/vadibook/diarize.py`:

```python
"""Stage 4: speaker diarization + one embedding per local speaker (pyannote.audio 4.x)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import soundfile as sf
import torch

from vadibook.models import DiarResult, DiarTurn

MODEL = "pyannote/speaker-diarization-community-1"
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from pyannote.audio import Pipeline

        token = os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError(
                "HF_TOKEN yok. https://huggingface.co/pyannote/speaker-diarization-community-1 "
                "koşullarını kabul et ve pipeline/.env içine HF_TOKEN yaz."
            )
        _pipeline = Pipeline.from_pretrained(MODEL, token=token)
        _pipeline.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    return _pipeline


def load_waveform(audio: Path) -> dict:
    """Decode any container to 16 kHz mono float32 via ffmpeg and hand pyannote an in-memory dict."""
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000", "-f", "wav", str(wav)],
            check=True,
        )
        data, sr = sf.read(str(wav), dtype="float32")
    return {"waveform": torch.from_numpy(data).unsqueeze(0), "sample_rate": sr}


def result_from_output(output) -> tuple[list[DiarTurn], dict[str, list[float]]]:
    """Adapt pyannote's DiarizeOutput (4.x) or a bare Annotation (3.x) to our models."""
    annotation = getattr(output, "exclusive_speaker_diarization", None) or output
    turns = [
        DiarTurn(start=float(seg.start), end=float(seg.end), speaker=str(label))
        for seg, _, label in annotation.itertracks(yield_label=True)
    ]
    embeddings: dict[str, list[float]] = {}
    vectors = getattr(output, "speaker_embeddings", None)
    if vectors is not None:
        labels = getattr(output, "speaker_diarization", annotation).labels()
        for label, vec in zip(labels, vectors):
            embeddings[str(label)] = [float(x) for x in vec]
    return turns, embeddings


def diarize(audio: Path) -> DiarResult:
    t0 = time.perf_counter()
    output = get_pipeline()(load_waveform(audio))
    turns, embeddings = result_from_output(output)
    return DiarResult(turns=turns, embeddings=embeddings, elapsed=time.perf_counter() - t0)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_diarize.py -v`
Expected: 3 passed.

- [ ] **Step 5: Add the `diarize` command to `cli.py`**

Add imports `from vadibook import diarize as diarize_mod` and extend the paths import to include `diar_path`; append before `if __name__`:

```python
@app.command()
def diarize(
    ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt,
) -> None:
    """pyannote ile konuşmacı ayrıştırma + konuşmacı embedding'leri → data/private/diar/."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        if state.is_done(e.key, "diarize") and not force:
            console.print(f"[dim]{e.id} diarize atlandı (bitmiş)[/]")
            continue
        if not state.is_done(e.key, "fetch"):
            console.print(f"[yellow]{e.id} diarize atlandı: önce fetch[/]")
            continue
        try:
            elapsed = 0.0
            speakers = 0
            for i, _ in enumerate(e.parts, start=1):
                result = diarize_mod.diarize(audio_path(e.key, i))
                diar_path(e.key, i).write_text(result.model_dump_json(), encoding="utf-8")
                elapsed += result.elapsed
                speakers += len({t.speaker for t in result.turns})
        except Exception as exc:  # noqa: BLE001
            state.record_error(e.key, "diarize", str(exc))
            console.print(f"[red]{e.id} diarize hata:[/] {exc}")
            continue
        dur = (state.stage_meta(e.key, "fetch") or {}).get("duration_sec") or 0.0
        rtf = elapsed / dur if dur else 0.0
        state.mark_done(e.key, "diarize", rtf=round(rtf, 4), elapsed=round(elapsed, 1), speakers=speakers)
        console.print(f"[green]{e.id}[/] diarize {elapsed/60:.1f} dk, RTF {rtf:.3f}, {speakers} konuşmacı")
```

- [ ] **Step 6: Commit**

```bash
git add pipeline/vadibook/diarize.py pipeline/vadibook/cli.py pipeline/tests/__init__.py pipeline/tests/test_diarize.py
git commit -m "feat(pipeline): pyannote diarization with per-speaker embeddings"
```

---

### Task 8: Align (words × speaker turns → utterances)

**Files:**
- Create: `pipeline/vadibook/align.py`
- Modify: `pipeline/vadibook/cli.py` (add `align` command)
- Test: `pipeline/tests/test_align.py`

**Interfaces:**
- Consumes: `models.AsrResult/DiarResult/Word/DiarTurn/Utterance`, `textnorm.normalize_tr/to_ascii`, `paths.asr_path/diar_path/utterances_path`.
- Produces: `align.words_from_asr(asr: AsrResult) -> list[Word]`; `align.speaker_at(turns: list[DiarTurn], t: float, *, snap: float = 0.5) -> str | None` (turns must be sorted by start); `align.assign_speakers(words, turns, *, max_gap: float = 1.5, max_dur: float = 30.0, snap: float = 0.5) -> list[tuple[str, list[Word]]]`; `align.build_utterances(ep_id: str, groups, *, part_no: int, offset: float, start_idx: int = 0) -> list[Utterance]`; `align.align_episode(ep: Episode) -> list[Utterance]` (reads asr+diar files for every part).
- Output `utterances/{key}.jsonl`: one `Utterance.model_dump_json()` per line.

- [ ] **Step 1: Write the failing tests**

`pipeline/tests/test_align.py`:

```python
from vadibook import align
from vadibook.models import AsrResult, AsrSegment, DiarTurn, Word


def w(text, start, end):
    return Word(word=text, start=start, end=end, probability=0.9)


TURNS = [DiarTurn(start=0.0, end=2.0, speaker="SPEAKER_00"), DiarTurn(start=2.5, end=5.0, speaker="SPEAKER_01")]


def test_speaker_at_inside_turn():
    assert align.speaker_at(TURNS, 1.0) == "SPEAKER_00"
    assert align.speaker_at(TURNS, 3.0) == "SPEAKER_01"


def test_speaker_at_snaps_to_nearby_turn_but_not_far():
    assert align.speaker_at(TURNS, 2.2) == "SPEAKER_00"  # 0.2s after turn 0 ends
    assert align.speaker_at(TURNS, 2.4) == "SPEAKER_01"  # closer to turn 1 start
    assert align.speaker_at(TURNS, 9.0) is None


def test_assign_groups_by_speaker_change():
    words = [w(" Gel", 0.1, 0.4), w(" buraya", 0.5, 0.9), w(" Geldim", 2.6, 3.0), w(" abi", 3.1, 3.4)]
    groups = align.assign_speakers(words, TURNS)
    assert [(spk, [x.word for x in ws]) for spk, ws in groups] == [
        ("SPEAKER_00", [" Gel", " buraya"]),
        ("SPEAKER_01", [" Geldim", " abi"]),
    ]


def test_assign_breaks_on_long_gap_and_max_duration():
    turns = [DiarTurn(start=0.0, end=100.0, speaker="SPEAKER_00")]
    words = [w(" a", 0.0, 0.5), w(" b", 3.0, 3.5)]  # gap 2.5s > max_gap
    assert len(align.assign_speakers(words, turns)) == 2
    long_words = [w(f" w{i}", i * 1.0, i * 1.0 + 0.5) for i in range(40)]  # 40s continuous
    assert len(align.assign_speakers(long_words, turns, max_dur=30.0)) == 2


def test_unmatched_word_inherits_previous_speaker():
    words = [w(" a", 1.0, 1.5), w(" b", 8.0, 8.5)]  # second word far from any turn
    groups = align.assign_speakers(words, TURNS)
    assert [g[0] for g in groups] == ["SPEAKER_00", "SPEAKER_00"]


def test_build_utterances_applies_offset_prefix_and_search_fields():
    groups = [("SPEAKER_03", [w(" Kâşifoğlu", 1.0, 1.8), w(" nerede?", 1.9, 2.3)])]
    utts = align.build_utterances("pusu/17", groups, part_no=2, offset=100.0, start_idx=5)
    u = utts[0]
    assert (u.ep, u.idx, u.speaker) == ("pusu/17", 5, "p2:SPEAKER_03")
    assert (u.start, u.end) == (101.0, 102.3)
    assert u.words[0].start == 101.0
    assert u.text == "Kâşifoğlu nerede?"
    assert u.text_norm == "kaşifoğlu nerede?"
    assert u.text_ascii == "kasifoglu nerede?"


def test_words_from_asr_falls_back_to_segment_when_no_words():
    asr = AsrResult(model="m", audio_duration=5, elapsed=1, segments=[
        AsrSegment(start=0, end=1, text=" Selam", avg_logprob=-0.1, no_speech_prob=0.0, compression_ratio=1.0,
                   words=[w(" Selam", 0.0, 1.0)]),
        AsrSegment(start=1, end=2, text=" Naber", avg_logprob=-0.1, no_speech_prob=0.0, compression_ratio=1.0),
    ])
    words = align.words_from_asr(asr)
    assert [x.word for x in words] == [" Selam", " Naber"]
    assert (words[1].start, words[1].end) == (1.0, 2.0)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_align.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'vadibook.align'`.

- [ ] **Step 3: Implement `align.py`**

`pipeline/vadibook/align.py`:

```python
"""Stage 5: give every whisper word a speaker and merge runs into utterances (pure functions + one file adapter)."""

from __future__ import annotations

import bisect
import re

from vadibook.models import AsrResult, DiarResult, DiarTurn, Episode, Utterance, Word
from vadibook.paths import asr_path, diar_path
from vadibook.textnorm import normalize_tr, to_ascii

_SPACES = re.compile(r"\s+")


def words_from_asr(asr: AsrResult) -> list[Word]:
    words: list[Word] = []
    for seg in asr.segments:
        if seg.words:
            words.extend(seg.words)
        else:  # defensive: whisper occasionally emits a segment without word timings
            words.append(Word(word=" " + seg.text.strip(), start=seg.start, end=seg.end, probability=0.0))
    return words


def speaker_at(turns: list[DiarTurn], t: float, *, snap: float = 0.5) -> str | None:
    """Speaker whose turn contains t; else the nearest turn edge within `snap` seconds; else None."""
    if not turns:
        return None
    starts = [x.start for x in turns]
    i = bisect.bisect_right(starts, t) - 1
    best: tuple[float, str] | None = None
    for j in (i, i + 1):
        if 0 <= j < len(turns):
            turn = turns[j]
            if turn.start <= t <= turn.end:
                return turn.speaker
            dist = min(abs(t - turn.start), abs(t - turn.end))
            if dist <= snap and (best is None or dist < best[0]):
                best = (dist, turn.speaker)
    return best[1] if best else None


def assign_speakers(
    words: list[Word],
    turns: list[DiarTurn],
    *,
    max_gap: float = 1.5,
    max_dur: float = 30.0,
    snap: float = 0.5,
) -> list[tuple[str, list[Word]]]:
    turns = sorted(turns, key=lambda x: x.start)
    groups: list[tuple[str, list[Word]]] = []
    prev = "UNK"
    for word in words:
        mid = (word.start + word.end) / 2
        spk = speaker_at(turns, mid, snap=snap) or prev
        if groups:
            cur_spk, cur_words = groups[-1]
            same = cur_spk == spk
            close = word.start - cur_words[-1].end <= max_gap
            short = word.end - cur_words[0].start <= max_dur
            if same and close and short:
                cur_words.append(word)
                prev = spk
                continue
        groups.append((spk, [word]))
        prev = spk
    return groups


def build_utterances(
    ep_id: str,
    groups: list[tuple[str, list[Word]]],
    *,
    part_no: int,
    offset: float,
    start_idx: int = 0,
) -> list[Utterance]:
    out: list[Utterance] = []
    for n, (spk, words) in enumerate(groups, start=start_idx):
        text = _SPACES.sub(" ", "".join(x.word for x in words)).strip()
        shifted = [x.model_copy(update={"start": x.start + offset, "end": x.end + offset}) for x in words]
        out.append(
            Utterance(
                ep=ep_id, idx=n, start=shifted[0].start, end=shifted[-1].end, speaker=f"p{part_no}:{spk}",
                text=text, text_norm=normalize_tr(text), text_ascii=to_ascii(text), words=shifted,
            )
        )
    return out


def align_episode(ep: Episode) -> list[Utterance]:
    utterances: list[Utterance] = []
    for i, part in enumerate(ep.parts, start=1):
        asr = AsrResult.model_validate_json(asr_path(ep.key, i).read_text(encoding="utf-8"))
        diar = DiarResult.model_validate_json(diar_path(ep.key, i).read_text(encoding="utf-8"))
        groups = assign_speakers(words_from_asr(asr), diar.turns)
        utterances.extend(
            build_utterances(ep.id, groups, part_no=i, offset=part.offset_sec, start_idx=len(utterances))
        )
    return utterances
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_align.py -v`
Expected: 7 passed.

- [ ] **Step 5: Add the `align` command to `cli.py`**

Add `from vadibook import align as align_mod` and extend the paths import with `utterances_path`; append before `if __name__`:

```python
@app.command()
def align(
    ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt,
) -> None:
    """ASR kelimelerini konuşmacı turn'leriyle birleştirip utterance JSONL üretir."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        if state.is_done(e.key, "align") and not force:
            console.print(f"[dim]{e.id} align atlandı (bitmiş)[/]")
            continue
        if not (state.is_done(e.key, "asr") and state.is_done(e.key, "diarize")):
            console.print(f"[yellow]{e.id} align atlandı: önce asr + diarize[/]")
            continue
        try:
            utts = align_mod.align_episode(e)
            with utterances_path(e.key).open("w", encoding="utf-8") as fh:
                for u in utts:
                    fh.write(u.model_dump_json() + "\n")
        except Exception as exc:  # noqa: BLE001
            state.record_error(e.key, "align", str(exc))
            console.print(f"[red]{e.id} align hata:[/] {exc}")
            continue
        speakers = len({u.speaker for u in utts})
        state.mark_done(e.key, "align", utterances=len(utts), speakers=speakers)
        console.print(f"[green]{e.id}[/] {len(utts)} utterance, {speakers} konuşmacı")
```

- [ ] **Step 6: Commit**

```bash
git add pipeline/vadibook/align.py pipeline/vadibook/cli.py pipeline/tests/test_align.py
git commit -m "feat(pipeline): align whisper words with diarization turns into utterances"
```

---

### Task 9: `run` + `status` commands, pipeline README

**Files:**
- Modify: `pipeline/vadibook/cli.py`
- Create: `pipeline/README.md`
- Test: `pipeline/tests/test_cli.py` (extend)

**Interfaces:**
- Produces: `cli.STAGES = ("fetch", "asr", "diarize", "align")`; command `run` (`--stages fetch,asr,diarize,align` default all; runs each stage function for the selected episodes in order, per episode, resumable); command `status` (rich table).
- Refactor: each stage command's per-episode body moves into `_fetch_one(e, episodes, sleep) -> list[Episode]`, `_asr_one(e, model, batch_size)`, `_diarize_one(e)`, `_align_one(e)` so `run` and the individual commands share code. The individual commands keep their exact behaviour.

- [ ] **Step 1: Write the failing tests**

Append to `pipeline/tests/test_cli.py`:

```python
from typer.testing import CliRunner

from vadibook import catalog, state
from vadibook.cli import app, parse_stages


def test_parse_stages_default_and_subset():
    assert parse_stages(None) == ("fetch", "asr", "diarize", "align")
    assert parse_stages("asr,align") == ("asr", "align")


def test_parse_stages_rejects_unknown():
    with pytest.raises(typer.BadParameter):
        parse_stages("asr,foo")


def test_status_lists_episodes_and_stage_marks(data_root):
    catalog.save_episodes(_eps())
    state.mark_done("pusu-001", "fetch", duration_sec=5400)
    state.mark_done("pusu-001", "asr", rtf=0.05)
    result = CliRunner().invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "pusu/1" in result.output
    assert "0.05" in result.output
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL, `ImportError: cannot import name 'parse_stages'`.

- [ ] **Step 3: Refactor `cli.py` into per-episode helpers and add `run`/`status`**

Replace the whole file:

```python
"""vadibook CLI. Each stage is idempotent per episode; `run` chains them and resumes after interruption."""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from vadibook import align as align_mod
from vadibook import asr as asr_mod
from vadibook import catalog as catalog_mod
from vadibook import diarize as diarize_mod
from vadibook import fetch as fetch_mod
from vadibook import state
from vadibook.models import Episode
from vadibook.paths import REPO_ROOT, asr_path, audio_path, diar_path, utterances_path

load_dotenv(REPO_ROOT / "pipeline" / ".env")

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Kurtlar Vadisi transkript pipeline'ı")
console = Console()

STAGES: tuple[str, ...] = ("fetch", "asr", "diarize", "align")

EpOpt = typer.Option([], "--ep", help="Bölüm id'si, tekrarlanabilir: --ep pusu/17 --ep kv/3")
AllOpt = typer.Option(False, "--all", help="Katalogdaki tüm bölümler")
SeriesOpt = typer.Option(None, "--series", help="Sadece bu seri: kv | pusu")
ForceOpt = typer.Option(False, "--force", help="Bitmiş aşamayı yeniden çalıştır")
ModelOpt = typer.Option("large-v3", "--model", help="faster-whisper modeli: large-v3 | large-v3-turbo")
BatchOpt = typer.Option(16, "--batch-size", help="Batched inference boyutu (VRAM'e göre)")
SleepOpt = typer.Option(5.0, "--sleep", help="İndirmeler arası bekleme (sn), YouTube throttling'e karşı")


def select_episodes(episodes: list[Episode], ep: list[str], all_: bool, series: str | None) -> list[Episode]:
    if ep:
        selected = [catalog_mod.find_episode(episodes, e) for e in ep]
    elif all_ or series:
        selected = list(episodes)
    else:
        raise typer.BadParameter("--ep SERİ/NO (tekrarlanabilir), --series veya --all ver")
    if series:
        selected = [e for e in selected if e.series == series]
    return selected


def parse_stages(spec: str | None) -> tuple[str, ...]:
    if not spec:
        return STAGES
    stages = tuple(s.strip() for s in spec.split(",") if s.strip())
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        raise typer.BadParameter(f"bilinmeyen aşama: {', '.join(unknown)} (geçerli: {', '.join(STAGES)})")
    return stages


def _replace_episode(episodes: list[Episode], updated: Episode) -> list[Episode]:
    return [updated if e.id == updated.id else e for e in episodes]


# --- per-episode stage bodies (shared by the stage commands and `run`) -------------------------

def _fetch_one(e: Episode, episodes: list[Episode], sleep: float) -> list[Episode]:
    updated = fetch_mod.fetch_episode(e, sleep=sleep)
    episodes = _replace_episode(episodes, updated)
    catalog_mod.save_episodes(episodes)
    total = sum(p.duration_sec or 0 for p in updated.parts)
    state.mark_done(e.key, "fetch", parts=len(updated.parts), duration_sec=total)
    console.print(f"[green]{e.id}[/] {len(updated.parts)} parça, {total/60:.1f} dk")
    return episodes


def _asr_one(e: Episode, model: str, batch_size: int) -> None:
    total_dur = total_elapsed = 0.0
    for i, _ in enumerate(e.parts, start=1):
        result = asr_mod.transcribe(audio_path(e.key, i), model_name=model, batch_size=batch_size)
        asr_path(e.key, i).write_text(result.model_dump_json(), encoding="utf-8")
        total_dur += result.audio_duration
        total_elapsed += result.elapsed
    rtf = total_elapsed / total_dur if total_dur else 0.0
    state.mark_done(e.key, "asr", model=model, rtf=round(rtf, 4), elapsed=round(total_elapsed, 1))
    console.print(f"[green]{e.id}[/] asr {total_elapsed/60:.1f} dk, RTF {rtf:.3f} ({1/rtf if rtf else 0:.0f}× gerçek zaman)")


def _diarize_one(e: Episode) -> None:
    elapsed = 0.0
    speakers = 0
    for i, _ in enumerate(e.parts, start=1):
        result = diarize_mod.diarize(audio_path(e.key, i))
        diar_path(e.key, i).write_text(result.model_dump_json(), encoding="utf-8")
        elapsed += result.elapsed
        speakers += len({t.speaker for t in result.turns})
    dur = (state.stage_meta(e.key, "fetch") or {}).get("duration_sec") or 0.0
    rtf = elapsed / dur if dur else 0.0
    state.mark_done(e.key, "diarize", rtf=round(rtf, 4), elapsed=round(elapsed, 1), speakers=speakers)
    console.print(f"[green]{e.id}[/] diarize {elapsed/60:.1f} dk, RTF {rtf:.3f}, {speakers} konuşmacı")


def _align_one(e: Episode) -> None:
    utts = align_mod.align_episode(e)
    with utterances_path(e.key).open("w", encoding="utf-8") as fh:
        for u in utts:
            fh.write(u.model_dump_json() + "\n")
    speakers = len({u.speaker for u in utts})
    state.mark_done(e.key, "align", utterances=len(utts), speakers=speakers)
    console.print(f"[green]{e.id}[/] {len(utts)} utterance, {speakers} konuşmacı")


_PREREQ = {"fetch": (), "asr": ("fetch",), "diarize": ("fetch",), "align": ("asr", "diarize")}


def _run_stage(stage: str, e: Episode, episodes: list[Episode], *, force: bool, model: str, batch_size: int, sleep: float) -> list[Episode]:
    """Run one stage for one episode with skip/prereq/error bookkeeping. Returns possibly-updated catalog."""
    if state.is_done(e.key, stage) and not force:
        console.print(f"[dim]{e.id} {stage} atlandı (bitmiş)[/]")
        return episodes
    missing = [p for p in _PREREQ[stage] if not state.is_done(e.key, p)]
    if missing:
        console.print(f"[yellow]{e.id} {stage} atlandı: önce {', '.join(missing)}[/]")
        return episodes
    try:
        if stage == "fetch":
            return _fetch_one(e, episodes, sleep)
        if stage == "asr":
            _asr_one(e, model, batch_size)
        elif stage == "diarize":
            _diarize_one(e)
        elif stage == "align":
            _align_one(e)
    except Exception as exc:  # noqa: BLE001 — record and keep the batch going
        state.record_error(e.key, stage, str(exc))
        console.print(f"[red]{e.id} {stage} hata:[/] {exc}")
    return episodes


# --- commands ---------------------------------------------------------------------------------

@app.command()
def catalog() -> None:
    """İki resmi playlist'i tarayıp data/public/episodes.json üretir; eksik/çift bölümleri raporlar."""
    entries = {series: catalog_mod.fetch_playlist(url) for series, url in catalog_mod.PLAYLISTS.items()}
    for series, items in entries.items():
        console.print(f"[bold]{series}[/]: {len(items)} video")
    episodes, warnings = catalog_mod.build_catalog(entries)
    catalog_mod.save_episodes(episodes)
    for w in warnings:
        console.print(f"[yellow]uyarı[/] {w}")
    missing = catalog_mod.gaps(episodes)
    if missing:
        console.print(f"[red]eksik {len(missing)} bölüm:[/] {', '.join(missing)}")
    console.print(f"[green]{len(episodes)} bölüm yazıldı[/] → {catalog_mod.episodes_file()}")


@app.command()
def fetch(ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt, sleep: float = SleepOpt) -> None:
    """Sesi (yalnız ses) ve otomatik TR altyazıyı indirir; parça sürelerini ölçüp episodes.json'ı günceller."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        episodes = _run_stage("fetch", e, episodes, force=force, model="", batch_size=0, sleep=sleep)


@app.command()
def asr(ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt, model: str = ModelOpt, batch_size: int = BatchOpt) -> None:
    """Sesi faster-whisper ile kelime zamanlı transkript eder → data/private/asr/."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        _run_stage("asr", e, episodes, force=force, model=model, batch_size=batch_size, sleep=0)


@app.command()
def diarize(ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt) -> None:
    """pyannote ile konuşmacı ayrıştırma + konuşmacı embedding'leri → data/private/diar/."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        _run_stage("diarize", e, episodes, force=force, model="", batch_size=0, sleep=0)


@app.command()
def align(ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt) -> None:
    """ASR kelimelerini konuşmacı turn'leriyle birleştirip utterance JSONL üretir."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        _run_stage("align", e, episodes, force=force, model="", batch_size=0, sleep=0)


@app.command()
def run(
    ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt,
    stages: str | None = typer.Option(None, "--stages", help="Virgülle: fetch,asr,diarize,align (varsayılan hepsi)"),
    model: str = ModelOpt, batch_size: int = BatchOpt, sleep: float = SleepOpt,
) -> None:
    """Seçili bölümler için aşamaları sırayla çalıştırır; kesilirse `state/` sayesinde kaldığı yerden devam eder."""
    wanted = parse_stages(stages)
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        for stage in wanted:
            episodes = _run_stage(stage, e, episodes, force=force, model=model, batch_size=batch_size, sleep=sleep)


@app.command()
def status(series: str | None = SeriesOpt) -> None:
    """Bölüm × aşama tablosu (RTF = işlem süresi / ses süresi)."""
    episodes = catalog_mod.load_episodes()
    if series:
        episodes = [e for e in episodes if e.series == series]
    table = Table(title="vadibook durum")
    for col in ("bölüm", "parça", "dk", "fetch", "asr (rtf)", "diarize (rtf)", "align (utt)", "hata"):
        table.add_column(col)
    done_counts = dict.fromkeys(STAGES, 0)
    for e in episodes:
        st = state.load(e.key)
        stages = st["stages"]
        for s in STAGES:
            done_counts[s] += s in stages
        dur = (stages.get("fetch") or {}).get("duration_sec")
        table.add_row(
            e.id, str(len(e.parts)), f"{dur/60:.0f}" if dur else "",
            "✓" if "fetch" in stages else "",
            f"{stages['asr'].get('rtf', '')}" if "asr" in stages else "",
            f"{stages['diarize'].get('rtf', '')}" if "diarize" in stages else "",
            f"{stages['align'].get('utterances', '')}" if "align" in stages else "",
            "; ".join(f"{k}: {v['message'][:40]}" for k, v in st["errors"].items()),
        )
    console.print(table)
    console.print(" · ".join(f"{s}: {done_counts[s]}/{len(episodes)}" for s in STAGES))


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run the whole test suite**

Run: `uv run pytest -v`
Expected: all pass (previous + 3 new cli tests).

- [ ] **Step 5: Write `pipeline/README.md`**

```markdown
# vadibook pipeline

Kurtlar Vadisi bölümlerini (resmi YouTube yüklemeleri) konuşmacı etiketli, kelime zamanlı
utterance'lara çevirir. Çıktılar `data/private/` altındadır ve **asla** repoya/siteye çıkmaz.

## Kurulum (Windows, RTX GPU)

```powershell
cd pipeline
uv python install 3.12
uv sync --group dev
copy .env.example .env   # HF_TOKEN doldur (pyannote model koşullarını kabul et)
$env:PYTHONUTF8 = "1"    # Türkçe konsol çıktısı için
uv run python -c "import torch; print(torch.cuda.is_available())"   # True olmalı
```

## Kullanım

```powershell
uv run vadibook catalog                      # playlist → data/public/episodes.json (+ eksik raporu)
uv run vadibook run --ep pusu/1              # tek bölüm: fetch → asr → diarize → align
uv run vadibook run --series pusu            # bir seri; kesilirse tekrar çalıştır, kaldığı yerden devam eder
uv run vadibook asr --ep pusu/1 --model large-v3-turbo --force
uv run vadibook status
uv run pytest
```

Aşama dosyaları: `audio/{key}.p{n}.opus` → `asr/{key}.p{n}.json` → `diar/{key}.p{n}.json` → `utterances/{key}.jsonl`;
ilerleme `state/{key}.json`.

## Sorun giderme

- `Could not load library cudnn_ops64_9.dll` / cuBLAS hatası: `asr.py` torch'u önce import eder; hâlâ hata
  varsa `uv add nvidia-cudnn-cu12 nvidia-cublas-cu12` ve `os.add_dll_directory(<site-packages>/nvidia/cudnn/bin)`.
- pyannote `torchcodec` import hatası: `diarize.py` sesi ffmpeg ile çözüp bellekten verir, torchcodec kullanılmaz;
  import yine kırılıyorsa `uv add "pyannote-audio==3.3.2"` + `MODEL="pyannote/speaker-diarization-3.1"` (embedding'siz).
- YouTube 429 / throttling: `--sleep 15`, gerekirse `cookies`.
```

- [ ] **Step 6: Commit**

```bash
git add pipeline/vadibook/cli.py pipeline/tests/test_cli.py pipeline/README.md
git commit -m "feat(pipeline): resumable run + status commands"
```

---

### Task 10: Faz 0 spike — one episode end to end, parameters fixed

**Files:**
- Create: `docs/superpowers/notes/2026-09-spike-findings.md`
- Possibly modify: `pipeline/vadibook/asr.py` (constants), `pipeline/vadibook/align.py` (defaults), `pipeline/README.md` (troubleshooting)

**Interfaces:** none new; this task produces measurements and locks constants.

- [ ] **Step 1: Prepare secrets**

Accept the model terms at https://huggingface.co/pyannote/speaker-diarization-community-1 (user action), create `pipeline/.env` with `HF_TOKEN=...`.

- [ ] **Step 2: Run the pipeline on one episode**

Run (from `pipeline/`): `uv run vadibook run --ep pusu/1`
Expected: four green lines. Note the printed RTF values. If any stage prints `hata`, read `data/private/state/pusu-001.json` → `errors`, fix per README troubleshooting, re-run the same command (finished stages are skipped).

- [ ] **Step 3: Check that YouTube auto subtitles exist (backup source)**

Run: `ls data/private/audio/` — expect `pusu-001.p1.tr.vtt` next to the `.opus`. Record yes/no in findings.

- [ ] **Step 4: Manual quality check (5 minutes of audio)**

Run: `uv run python -c "import json,itertools; [print(f\"{json.loads(l)['start']:7.1f} {json.loads(l)['speaker']:14} {json.loads(l)['text']}\") for l in itertools.islice(open('../data/private/utterances/pusu-001.jsonl',encoding='utf-8'), 0, 80)]"`
Open the episode on YouTube at the same timestamps and compare. Count: wrong/missing words per 100, obvious speaker-boundary errors, hallucinated lines. Look specifically at how proper names came out (Polat, Memati, Kaşifoğlu). Write numbers into the findings file.

- [ ] **Step 5: Compare `large-v3-turbo`**

Run: `uv run vadibook asr --ep pusu/1 --model large-v3-turbo --force` then `uv run vadibook align --ep pusu/1 --force`, repeat Step 4 on the same 80 utterances. Record RTF and quality side by side. Decision rule: keep `large-v3` unless turbo's error count is within +10 % and RTF at least 1.7× better.

- [ ] **Step 6: Measure VRAM headroom**

While Step 5's asr runs: `nvidia-smi --query-gpu=memory.used --format=csv -l 5`. If peak > 10 GB, lower `--batch-size` to 8 and note it as the default.

- [ ] **Step 7: Write the findings note**

`docs/superpowers/notes/2026-09-spike-findings.md`:

```markdown
# Faz 0 spike bulguları — pusu/1

| Ölçüm | large-v3 | large-v3-turbo |
|---|---|---|
| ASR RTF | | |
| Diarize RTF | | |
| Peak VRAM | | |
| Hatalı/eksik kelime (80 utterance) | | |
| Konuşmacı sınır hatası | | |
| Halüsinasyon satırı | | |
| Özel isimler (Polat/Memati/Kaşifoğlu) | | |

Otomatik TR altyazı mevcut: evet/hayır

## Karar
- ASR modeli: ...
- batch_size: ...
- Değişen sabitler: ...
- 397 bölüm tahmini GPU süresi: (toplam saat × RTF_asr + toplam saat × RTF_diar)

## Sürprizler / dead end'ler
- ...
```

Fill every cell with the measured value (no blanks). Apply any constant changes to `asr.py` / `align.py` / `cli.py` defaults, and re-run `uv run pytest`.

- [ ] **Step 8: Commit and hand off**

```bash
git add docs/superpowers/notes/2026-09-spike-findings.md pipeline/
git commit -m "docs: record Faz 0 spike findings and lock ASR defaults"
```

Then in todox: `update_task(300, status: 'done')`, `log_entry(kind:'decision')` with the model choice and why, `log_entry(kind:'dead_end')` for anything that failed (DLL issues, torchcodec, throttling).

---

### Task 11: Faz 1 — full catalog check and batch run

**Files:** none new (operations task; `data/public/episodes.json` changes).

- [ ] **Step 1: Verify the catalog is complete**

Run: `uv run vadibook catalog`
Expected: `eksik` line absent, or lists ≤ a handful. For each missing number, search the playlist page manually; if the video exists under an odd title, add a parametrised case to `test_parse_title`, extend the regex in `catalog.py`, re-run. If the video genuinely is not on the official playlists, add the id to a `MISSING.md` note under `data/public/` with the reason — do not substitute non-official uploads.

- [ ] **Step 2: Download all audio in the background**

Run: `uv run vadibook fetch --all --sleep 8`
Expected: hours (397 × ~40 MB + sleeps). Re-run the same command after any interruption; finished episodes are skipped. Watch for `hata` lines with 429 → raise `--sleep`.

- [ ] **Step 3: Transcribe + diarize + align everything**

Run: `uv run vadibook run --all --stages asr,diarize,align --model <from spike>`
Expected: per the spike estimate (tens of GPU hours). The command is safe to stop and restart. Check progress with `uv run vadibook status --series pusu`.

- [ ] **Step 4: Sanity checks on the corpus**

Run: `uv run python -c "import glob,json; n=0; s=set(); [ (n:=n+1, s.add(json.loads(l)['speaker'])) for f in glob.glob('../data/private/utterances/*.jsonl') for l in open(f,encoding='utf-8')]; print(n, 'utterances')"`
Expected: on the order of 10⁵–10⁶ utterances. Spot-check three random episodes as in Task 10 Step 4.

- [ ] **Step 5: Commit the updated catalog and hand off**

```bash
git add data/public/episodes.json
git commit -m "data: measured part durations for all catalogued episodes"
```

todox: `update_task(301, status:'done')` with a handoff entry stating the corpus size, total GPU hours, and any episodes that failed (from `vadibook status` error column) so Faz 2 (task #302) can start from `build`.

---

## Self-review

- **Spec coverage:** catalog (§1) → Task 4; fetch + auto-subs + throttling (§2) → Task 5; ASR large-v3/turbo, VAD, hallucination thresholds, `initial_prompt` with character names (§3, "Kalite") → Task 6; pyannote + embeddings, own alignment instead of WhisperX (§4) → Task 7; align merge rules, `text_norm` (§5) → Tasks 2, 8; idempotent per-episode state + `run --all` resumable → Tasks 3, 9; multi-part offsets → Tasks 4, 5, 8; Python 3.12 pin → Task 1; Faz 0 measurements and Faz 1 batch → Tasks 10, 11. `text_ascii` is produced here so Faz 2's `build` does not recompute it.
- **Placeholder scan:** the only intentionally empty cells are the spike findings table, which Task 10 Step 7 requires to be filled before commit.
- **Type consistency:** `select_episodes(episodes, ep, all_, series)` used identically in Tasks 5 and 9; `state.mark_done(key, stage, **meta)` / `stage_meta` / `record_error` names match Task 3; `paths.audio_path(key, part)` etc. match Task 1; `DiarResult.embeddings: dict[str, list[float]]` matches Task 7's `result_from_output`; `Utterance.speaker` format `p{part}:{label}` matches Tasks 2 and 8; `fetch._download(yt_id, out, sleep)` signature matches the monkeypatch in `test_fetch.py`.
