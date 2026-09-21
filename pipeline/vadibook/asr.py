"""Stage 3: faster-whisper transcription with word timestamps.

Windows note: ctranslate2 needs cuBLAS/cuDNN DLLs. Importing torch first puts the ones shipped
in torch/lib on the loader path, which is why `import torch` sits above `faster_whisper`.
"""

from __future__ import annotations

import time
from pathlib import Path

import torch  # imported before faster_whisper on purpose (see module docstring)

from vadibook.models import AsrResult, AsrSegment, Word
from vadibook.textnorm import normalize_tr

# Whisper's well-known Turkish hallucinations on music/silence (subtitle credits, outros).
HALLUCINATION_BLOCKLIST: tuple[str, ...] = (
    "altyazı m.k",
    "altyazı: m.k",
    "izlediğiniz için teşekkür",
    "abone olmayı unutmayın",
)

# Proper names bias the decoder toward the show's vocabulary (spec "Kalite" risk).
INITIAL_PROMPT = (
    "Kurtlar Vadisi Pusu. Polat Alemdar, Memati Baş, Abdülhey Çoban, Süleyman Çakır, Laz Ziya, "
    "İskender Büyük, Kaşifoğlu, Aron Feller, Ömer Baba, Elif Eylül, Tapınakçılar, KGT."
)

# Silero VAD at its default 0.5 threshold misses dialogue under the show's loud score; 0.3 recovered
# ~70% more words on a music-heavy slice of pusu/1 with no extra hallucinations (spike, 2026-09-21).
VAD_OPTIONS: dict = {"threshold": 0.3, "min_silence_duration_ms": 1000, "speech_pad_ms": 400}

_pipelines: dict[str, object] = {}


def get_pipeline(model_name: str):
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    if model_name not in _pipelines:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute = "float16" if device == "cuda" else "int8"
        _pipelines[model_name] = BatchedInferencePipeline(
            model=WhisperModel(model_name, device=device, compute_type=compute)
        )
    return _pipelines[model_name]


def filter_segments(
    segments: list[AsrSegment],
    *,
    no_speech_max: float = 0.6,
    logprob_min: float = -1.0,
    compression_max: float = 2.4,
    blocklist: tuple[str, ...] = HALLUCINATION_BLOCKLIST,
) -> list[AsrSegment]:
    """Drop silence/hallucination segments. Whisper's own rule for "silent" is
    no_speech_prob > threshold AND avg_logprob < logprob_min; a confident decode under music is speech.
    """
    kept: list[AsrSegment] = []
    for s in segments:
        text = normalize_tr(s.text).strip()
        if not text:
            continue
        if s.no_speech_prob > no_speech_max and s.avg_logprob < logprob_min:
            continue
        if s.compression_ratio > compression_max:
            continue
        if any(b in text for b in blocklist):
            continue
        kept.append(s)
    return kept


def transcribe(audio: Path, *, model_name: str = "large-v3-turbo", batch_size: int = 16) -> AsrResult:
    """Raw transcription: every decoded segment is kept (whisper's internal silence/logprob drops are
    disabled) so `filter_segments` can be re-tuned at align time without re-running the GPU."""
    t0 = time.perf_counter()
    segments_iter, info = get_pipeline(model_name).transcribe(
        str(audio),
        language="tr",
        batch_size=batch_size,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(VAD_OPTIONS),
        no_speech_threshold=1.0,
        log_prob_threshold=None,
        initial_prompt=INITIAL_PROMPT,
    )
    segments = [
        AsrSegment(
            start=s.start, end=s.end, text=s.text,
            avg_logprob=s.avg_logprob, no_speech_prob=s.no_speech_prob, compression_ratio=s.compression_ratio,
            words=[Word(word=w.word, start=w.start, end=w.end, probability=w.probability) for w in (s.words or [])],
        )
        for s in segments_iter  # transcription actually runs while iterating
    ]
    return AsrResult(
        model=model_name,
        audio_duration=float(info.duration),
        elapsed=time.perf_counter() - t0,
        segments=segments,
    )
