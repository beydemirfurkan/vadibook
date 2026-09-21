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
