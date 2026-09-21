"""Stage 4: speaker diarization + one embedding per local speaker (pyannote.audio 4.x)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import soundfile as sf
import torch

from vadibook.models import DiarResult, DiarTurn

MODEL = "pyannote/speaker-diarization-community-1"
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from pyannote.audio import Pipeline

        token = os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError(
                "HF_TOKEN yok. https://huggingface.co/pyannote/speaker-diarization-community-1 "
                "koşullarını kabul et ve pipeline/.env içine HF_TOKEN yaz."
            )
        _pipeline = Pipeline.from_pretrained(MODEL, token=token)
        _pipeline.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    return _pipeline


def load_waveform(audio: Path) -> dict:
    """Decode any container to 16 kHz mono float32 via ffmpeg and hand pyannote an in-memory dict."""
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000", "-f", "wav", str(wav)],
            check=True,
        )
        data, sr = sf.read(str(wav), dtype="float32")
    return {"waveform": torch.from_numpy(data).unsqueeze(0), "sample_rate": sr}


def result_from_output(output) -> tuple[list[DiarTurn], dict[str, list[float]]]:
    """Adapt pyannote's DiarizeOutput (4.x) or a bare Annotation (3.x) to our models."""
    annotation = getattr(output, "exclusive_speaker_diarization", None) or output
    turns = [
        DiarTurn(start=float(seg.start), end=float(seg.end), speaker=str(label))
        for seg, _, label in annotation.itertracks(yield_label=True)
    ]
    embeddings: dict[str, list[float]] = {}
    vectors = getattr(output, "speaker_embeddings", None)
    if vectors is not None:
        labels = getattr(output, "speaker_diarization", annotation).labels()
        for label, vec in zip(labels, vectors):
            embeddings[str(label)] = [float(x) for x in vec]
    return turns, embeddings


def diarize(audio: Path) -> DiarResult:
    t0 = time.perf_counter()
    output = get_pipeline()(load_waveform(audio))
    turns, embeddings = result_from_output(output)
    return DiarResult(turns=turns, embeddings=embeddings, elapsed=time.perf_counter() - t0)
