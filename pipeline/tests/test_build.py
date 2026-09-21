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
            u = Utterance(
                ep=ep.id, idx=i, start=start, end=end, speaker=spk, text=text, text_norm=text.lower(),
                text_ascii=text.lower(), words=[Word(word=text, start=start, end=end, probability=1)],
            )
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
    assert docs[0] == {
        "id": "pusu-001:000000", "series": "pusu", "ep": 1, "ep_key": "pusu-001", "part": 1,
        "start": 1.0, "end": 2.0, "speaker": "p1:SPEAKER_00", "text": "Kaşifoğlu nerede",
        "text_ascii": "kaşifoğlu nerede", "yt_url": "https://youtu.be/abc?t=1",
    }


def test_meili_settings_do_not_search_ids():
    assert set(build.MEILI_SETTINGS["searchableAttributes"]) == {"text", "text_ascii"}
    assert "ep_key" in build.MEILI_SETTINGS["filterableAttributes"]
