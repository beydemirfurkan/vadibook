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
