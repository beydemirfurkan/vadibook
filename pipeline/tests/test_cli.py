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
