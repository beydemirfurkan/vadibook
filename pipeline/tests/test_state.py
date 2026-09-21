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
