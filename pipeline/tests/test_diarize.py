from types import SimpleNamespace

import numpy as np

from tests.test_fetch import make_tone
from vadibook import diarize


def test_load_audio_is_mono_16k_float32(tmp_path):
    wav = make_tone(tmp_path / "t.wav", 1.0)
    audio, sr = diarize.load_audio(wav)
    assert sr == 16000
    assert audio.dtype == np.float32
    assert audio.ndim == 1
    assert abs(len(audio) - 16000) < 100


def test_turns_from_segments_labels_like_pyannote():
    segs = [SimpleNamespace(start=0.0, end=1.0, speaker=1), SimpleNamespace(start=1.5, end=2.0, speaker=0)]
    turns = diarize.turns_from_segments(segs)
    assert [(t.start, t.end, t.speaker) for t in turns] == [(0.0, 1.0, "SPEAKER_01"), (1.5, 2.0, "SPEAKER_00")]


class FakeStream:
    def __init__(self):
        self.samples = None

    def accept_waveform(self, sample_rate, waveform):
        self.samples = waveform

    def input_finished(self):
        pass


class FakeExtractor:
    """Embedding = [mean sample value, 1.0]; lets the test see which audio slice was used."""

    def create_stream(self):
        return FakeStream()

    def is_ready(self, stream):
        return True

    def compute(self, stream):
        return [float(stream.samples.mean()), 1.0]


def test_speaker_embeddings_average_long_turns_and_skip_short_ones():
    sr = 16000
    audio = np.zeros(sr * 10, dtype=np.float32)
    audio[0 : sr * 2] = 0.5  # speaker A talks 0-2 s (value 0.5)
    audio[sr * 3 : sr * 5] = -0.5  # speaker B talks 3-5 s (value -0.5)
    turns = diarize.turns_from_segments(
        [
            SimpleNamespace(start=0.0, end=2.0, speaker=0),
            SimpleNamespace(start=3.0, end=5.0, speaker=1),
            SimpleNamespace(start=6.0, end=6.4, speaker=1),  # < min_dur, ignored
        ]
    )
    emb = diarize.speaker_embeddings(audio, sr, turns, FakeExtractor(), min_dur=1.0)
    assert set(emb) == {"SPEAKER_00", "SPEAKER_01"}
    a, b = np.array(emb["SPEAKER_00"]), np.array(emb["SPEAKER_01"])
    assert np.isclose(np.linalg.norm(a), 1.0) and np.isclose(np.linalg.norm(b), 1.0)  # L2-normalised
    assert a[0] > 0 > b[0]  # built from each speaker's own audio


def test_speaker_embeddings_caps_audio_per_speaker():
    sr = 16000
    audio = np.ones(sr * 100, dtype=np.float32)
    turns = diarize.turns_from_segments([SimpleNamespace(start=i * 10.0, end=i * 10.0 + 9.0, speaker=0) for i in range(10)])
    used = []

    class CountingExtractor(FakeExtractor):
        def compute(self, stream):
            used.append(len(stream.samples) / sr)
            return [1.0, 0.0]

    diarize.speaker_embeddings(audio, sr, turns, CountingExtractor(), min_dur=1.0, max_total=30.0)
    assert sum(used) <= 30.0 + 9.0  # stops once the cap is reached
