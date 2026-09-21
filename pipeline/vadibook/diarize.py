"""Stage 4: speaker diarization + one embedding per local speaker, fully local via sherpa-onnx.

Models are the MIT-licensed pyannote `segmentation-3.0` (ONNX export redistributed by k2-fsa) and the
WeSpeaker VoxCeleb ResNet34-LM embedding model pyannote 3.1 itself uses. No Hugging Face account or
token is needed; the files are downloaded once into data/private/models/.
"""

from __future__ import annotations

import os
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

from vadibook.models import DiarResult, DiarTurn
from vadibook.paths import private_dir

_RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
SEG_URL = f"{_RELEASES}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
EMB_URL = f"{_RELEASES}/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx"

# Agglomerative clustering distance threshold (cosine). Tuned later against the labelled voice bank.
CLUSTER_THRESHOLD = 0.7
NUM_THREADS = max(4, (os.cpu_count() or 8) // 2)

_diarizer = None
_extractor = None


def models_dir() -> Path:
    return private_dir("models")


def seg_model_path() -> Path:
    return models_dir() / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx"


def emb_model_path() -> Path:
    return models_dir() / "wespeaker_en_voxceleb_resnet34_LM.onnx"


def ensure_models() -> None:
    """Download the two ONNX models on first use (≈31 MB total)."""
    if not seg_model_path().exists():
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "seg.tar.bz2"
            urllib.request.urlretrieve(SEG_URL, archive)
            with tarfile.open(archive, "r:bz2") as tar:
                tar.extractall(models_dir(), filter="data")
    if not emb_model_path().exists():
        urllib.request.urlretrieve(EMB_URL, emb_model_path())


def get_diarizer(num_threads: int = NUM_THREADS):
    global _diarizer
    if _diarizer is None:
        import sherpa_onnx

        ensure_models()
        cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(seg_model_path())),
                num_threads=num_threads,
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(emb_model_path()), num_threads=num_threads),
            clustering=sherpa_onnx.FastClusteringConfig(num_clusters=-1, threshold=CLUSTER_THRESHOLD),
            min_duration_on=0.3,
            min_duration_off=0.5,
        )
        if not cfg.validate():
            raise RuntimeError("sherpa-onnx diarization config geçersiz (model dosyaları eksik?)")
        _diarizer = sherpa_onnx.OfflineSpeakerDiarization(cfg)
    return _diarizer


def get_extractor(num_threads: int = NUM_THREADS):
    global _extractor
    if _extractor is None:
        import sherpa_onnx

        ensure_models()
        cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(emb_model_path()), num_threads=num_threads)
        _extractor = sherpa_onnx.SpeakerEmbeddingExtractor(cfg)
    return _extractor


def load_audio(audio: Path) -> tuple[np.ndarray, int]:
    """Decode any container to 16 kHz mono float32 via ffmpeg."""
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000", "-f", "wav", str(wav)],
            check=True,
        )
        data, sr = sf.read(str(wav), dtype="float32")
    if data.ndim > 1:
        data = data[:, 0]
    return np.ascontiguousarray(data, dtype=np.float32), int(sr)


def turns_from_segments(segments) -> list[DiarTurn]:
    """sherpa-onnx segments (start, end, int speaker) → DiarTurn with pyannote-style labels."""
    return [
        DiarTurn(start=float(s.start), end=float(s.end), speaker=f"SPEAKER_{int(s.speaker):02d}")
        for s in segments
    ]


def speaker_embeddings(
    audio: np.ndarray,
    sr: int,
    turns: list[DiarTurn],
    extractor,
    *,
    min_dur: float = 1.0,
    max_total: float = 60.0,
) -> dict[str, list[float]]:
    """One L2-normalised embedding per speaker: duration-weighted mean over its longest turns.

    Turns shorter than `min_dur` are skipped (too little voice); at most `max_total` seconds of audio
    per speaker are embedded so a lead character does not cost minutes of CPU.
    """
    by_speaker: dict[str, list[DiarTurn]] = {}
    for t in turns:
        if t.end - t.start >= min_dur:
            by_speaker.setdefault(t.speaker, []).append(t)
    out: dict[str, list[float]] = {}
    for spk, spk_turns in by_speaker.items():
        acc = None
        used = 0.0
        for t in sorted(spk_turns, key=lambda x: x.end - x.start, reverse=True):
            if used >= max_total:
                break
            chunk = audio[int(t.start * sr) : int(t.end * sr)]
            if len(chunk) == 0:
                continue
            stream = extractor.create_stream()
            stream.accept_waveform(sample_rate=sr, waveform=chunk)
            stream.input_finished()
            if not extractor.is_ready(stream):
                continue
            vec = np.asarray(extractor.compute(stream), dtype=np.float64)
            dur = t.end - t.start
            acc = vec * dur if acc is None else acc + vec * dur
            used += dur
        if acc is not None:
            norm = np.linalg.norm(acc)
            out[spk] = [float(x) for x in (acc / norm if norm else acc)]
    return out


def diarize(audio_path: Path) -> DiarResult:
    t0 = time.perf_counter()
    audio, sr = load_audio(audio_path)
    diarizer = get_diarizer()
    if sr != diarizer.sample_rate:
        raise RuntimeError(f"beklenen örnekleme {diarizer.sample_rate}, gelen {sr}")
    segments = diarizer.process(audio).sort_by_start_time()
    turns = turns_from_segments(segments)
    embeddings = speaker_embeddings(audio, sr, turns, get_extractor())
    return DiarResult(turns=turns, embeddings=embeddings, elapsed=time.perf_counter() - t0)
