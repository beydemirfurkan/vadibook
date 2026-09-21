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
