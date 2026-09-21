"""Pydantic models shared by every stage. Times are seconds (float)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Series = Literal["kv", "pusu"]


class EpisodePart(BaseModel):
    """One YouTube video. Most episodes have exactly one part."""

    yt_id: str
    title: str
    offset_sec: float = 0.0  # where this part starts on the episode-global timeline
    duration_sec: float | None = None  # playlist estimate until `fetch` probes the file


class Episode(BaseModel):
    series: Series
    no: int
    parts: list[EpisodePart] = Field(min_length=1)

    @property
    def key(self) -> str:
        """Filesystem-safe id: pusu-017."""
        return f"{self.series}-{self.no:03d}"

    @property
    def id(self) -> str:
        """Human/CLI id: pusu/17."""
        return f"{self.series}/{self.no}"


class Word(BaseModel):
    word: str  # as emitted by whisper, usually with a leading space
    start: float
    end: float
    probability: float


class AsrSegment(BaseModel):
    start: float
    end: float
    text: str
    avg_logprob: float
    no_speech_prob: float
    compression_ratio: float
    words: list[Word] = []


class AsrResult(BaseModel):
    model: str
    audio_duration: float
    elapsed: float
    segments: list[AsrSegment]


class DiarTurn(BaseModel):
    start: float
    end: float
    speaker: str  # local label from pyannote, e.g. SPEAKER_00


class DiarResult(BaseModel):
    turns: list[DiarTurn]
    embeddings: dict[str, list[float]]  # local speaker label -> embedding vector
    elapsed: float


class Utterance(BaseModel):
    ep: str  # episode id, e.g. pusu/17
    idx: int  # 0-based, global across parts
    start: float  # episode-global seconds
    end: float
    speaker: str  # "p{part}:{local label}", e.g. p1:SPEAKER_03
    text: str
    text_norm: str
    text_ascii: str
    words: list[Word]
