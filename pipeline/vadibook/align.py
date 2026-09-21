"""Stage 5: give every whisper word a speaker and merge runs into utterances (pure functions + one file adapter)."""

from __future__ import annotations

import bisect
import re

from vadibook.models import AsrResult, DiarResult, DiarTurn, Episode, Utterance, Word
from vadibook.paths import asr_path, diar_path
from vadibook.textnorm import normalize_tr, to_ascii

_SPACES = re.compile(r"\s+")


def words_from_asr(asr: AsrResult) -> list[Word]:
    words: list[Word] = []
    for seg in asr.segments:
        if seg.words:
            words.extend(seg.words)
        else:  # defensive: whisper occasionally emits a segment without word timings
            words.append(Word(word=" " + seg.text.strip(), start=seg.start, end=seg.end, probability=0.0))
    return words


def speaker_at(turns: list[DiarTurn], t: float, *, snap: float = 0.5) -> str | None:
    """Speaker whose turn contains t; else the nearest turn edge within `snap` seconds; else None."""
    if not turns:
        return None
    starts = [x.start for x in turns]
    i = bisect.bisect_right(starts, t) - 1
    best: tuple[float, str] | None = None
    for j in (i, i + 1):
        if 0 <= j < len(turns):
            turn = turns[j]
            if turn.start <= t <= turn.end:
                return turn.speaker
            dist = min(abs(t - turn.start), abs(t - turn.end))
            if dist <= snap and (best is None or dist < best[0]):
                best = (dist, turn.speaker)
    return best[1] if best else None


def assign_speakers(
    words: list[Word],
    turns: list[DiarTurn],
    *,
    max_gap: float = 1.5,
    max_dur: float = 30.0,
    snap: float = 0.5,
) -> list[tuple[str, list[Word]]]:
    turns = sorted(turns, key=lambda x: x.start)
    groups: list[tuple[str, list[Word]]] = []
    prev = "UNK"
    for word in words:
        mid = (word.start + word.end) / 2
        spk = speaker_at(turns, mid, snap=snap) or prev
        if groups:
            cur_spk, cur_words = groups[-1]
            same = cur_spk == spk
            close = word.start - cur_words[-1].end <= max_gap
            short = word.end - cur_words[0].start <= max_dur
            if same and close and short:
                cur_words.append(word)
                prev = spk
                continue
        groups.append((spk, [word]))
        prev = spk
    return groups


def build_utterances(
    ep_id: str,
    groups: list[tuple[str, list[Word]]],
    *,
    part_no: int,
    offset: float,
    start_idx: int = 0,
) -> list[Utterance]:
    out: list[Utterance] = []
    for n, (spk, words) in enumerate(groups, start=start_idx):
        text = _SPACES.sub(" ", "".join(x.word for x in words)).strip()
        shifted = [x.model_copy(update={"start": x.start + offset, "end": x.end + offset}) for x in words]
        out.append(
            Utterance(
                ep=ep_id, idx=n, start=shifted[0].start, end=shifted[-1].end, speaker=f"p{part_no}:{spk}",
                text=text, text_norm=normalize_tr(text), text_ascii=to_ascii(text), words=shifted,
            )
        )
    return out


def align_episode(ep: Episode) -> list[Utterance]:
    utterances: list[Utterance] = []
    for i, part in enumerate(ep.parts, start=1):
        asr = AsrResult.model_validate_json(asr_path(ep.key, i).read_text(encoding="utf-8"))
        diar = DiarResult.model_validate_json(diar_path(ep.key, i).read_text(encoding="utf-8"))
        groups = assign_speakers(words_from_asr(asr), diar.turns)
        utterances.extend(
            build_utterances(ep.id, groups, part_no=i, offset=part.offset_sec, start_idx=len(utterances))
        )
    return utterances
