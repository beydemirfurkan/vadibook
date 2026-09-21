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
