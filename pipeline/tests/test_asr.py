from vadibook.asr import filter_segments
from vadibook.models import AsrSegment


def seg(text, *, no_speech=0.1, comp=1.2, logprob=-0.3):
    return AsrSegment(start=0, end=1, text=text, avg_logprob=logprob, no_speech_prob=no_speech, compression_ratio=comp)


def test_keeps_ordinary_speech():
    out = filter_segments([seg(" Polat, gel buraya.")])
    assert [s.text for s in out] == [" Polat, gel buraya."]


def test_drops_high_no_speech_prob_only_when_decoder_is_also_unsure():
    # whisper's canonical rule: silent iff no_speech_prob > 0.6 AND avg_logprob < -1.0
    assert filter_segments([seg("...", no_speech=0.9, logprob=-1.4)]) == []
    kept = filter_segments([seg(" Vatan için.", no_speech=0.9, logprob=-0.2)])  # speech under loud music
    assert len(kept) == 1


def test_drops_repetitive_output():
    assert filter_segments([seg("evet evet evet evet evet", comp=3.1)]) == []


def test_drops_known_turkish_whisper_hallucinations_case_insensitively():
    assert filter_segments([seg(" Altyazı M.K."), seg("ALTYAZI M.K"), seg(" İzlediğiniz için teşekkürler.")]) == []


def test_drops_empty_text():
    assert filter_segments([seg("   ")]) == []
