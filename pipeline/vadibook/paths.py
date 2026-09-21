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
