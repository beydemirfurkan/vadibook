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
