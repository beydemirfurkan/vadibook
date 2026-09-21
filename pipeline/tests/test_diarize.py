from types import SimpleNamespace

import numpy as np
import torch

from tests.test_fetch import make_tone
from vadibook import diarize


def test_load_waveform_is_mono_16k(tmp_path):
    wav = make_tone(tmp_path / "t.wav", 1.0)
    out = diarize.load_waveform(wav)
    assert out["sample_rate"] == 16000
    assert isinstance(out["waveform"], torch.Tensor)
    assert out["waveform"].shape[0] == 1
    assert abs(out["waveform"].shape[1] - 16000) < 100


class FakeSegment:
    def __init__(self, start, end):
        self.start, self.end = start, end


class FakeAnnotation:
    def __init__(self, tracks):
        self._tracks = tracks  # list of (start, end, label)

    def itertracks(self, yield_label=False):
        for s, e, lab in self._tracks:
            yield FakeSegment(s, e), "track", lab

    def labels(self):
        return sorted({lab for _, _, lab in self._tracks})


def test_result_from_diarize_output_uses_exclusive_turns_and_embeddings():
    exclusive = FakeAnnotation([(0.0, 1.0, "SPEAKER_00"), (1.0, 2.0, "SPEAKER_01")])
    full = FakeAnnotation([(0.0, 1.2, "SPEAKER_00"), (0.9, 2.0, "SPEAKER_01")])
    output = SimpleNamespace(
        speaker_diarization=full,
        exclusive_speaker_diarization=exclusive,
        speaker_embeddings=np.array([[1.0, 0.0], [0.0, 1.0]]),
    )
    turns, emb = diarize.result_from_output(output)
    assert [(t.start, t.end, t.speaker) for t in turns] == [(0.0, 1.0, "SPEAKER_00"), (1.0, 2.0, "SPEAKER_01")]
    assert emb == {"SPEAKER_00": [1.0, 0.0], "SPEAKER_01": [0.0, 1.0]}


def test_result_from_plain_annotation_has_no_embeddings():
    ann = FakeAnnotation([(0.0, 1.0, "SPEAKER_00")])
    turns, emb = diarize.result_from_output(ann)
    assert len(turns) == 1 and emb == {}
