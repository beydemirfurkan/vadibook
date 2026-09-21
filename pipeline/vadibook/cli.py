"""vadibook CLI. Each stage command is idempotent per episode; see `vadibook run`."""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console

from vadibook import align as align_mod
from vadibook import asr as asr_mod
from vadibook import catalog as catalog_mod
from vadibook import diarize as diarize_mod
from vadibook import fetch as fetch_mod
from vadibook import state
from vadibook.models import Episode
from vadibook.paths import REPO_ROOT, asr_path, audio_path, diar_path, utterances_path

load_dotenv(REPO_ROOT / "pipeline" / ".env")

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Kurtlar Vadisi transkript pipeline'ı")
console = Console()

EpOpt = typer.Option([], "--ep", help="Bölüm id'si, tekrarlanabilir: --ep pusu/17 --ep kv/3")
AllOpt = typer.Option(False, "--all", help="Katalogdaki tüm bölümler")
SeriesOpt = typer.Option(None, "--series", help="Sadece bu seri: kv | pusu")
ForceOpt = typer.Option(False, "--force", help="Bitmiş aşamayı yeniden çalıştır")


def select_episodes(episodes: list[Episode], ep: list[str], all_: bool, series: str | None) -> list[Episode]:
    if ep:
        selected = [catalog_mod.find_episode(episodes, e) for e in ep]
    elif all_ or series:
        selected = list(episodes)
    else:
        raise typer.BadParameter("--ep SERİ/NO (tekrarlanabilir), --series veya --all ver")
    if series:
        selected = [e for e in selected if e.series == series]
    return selected


def _replace_episode(episodes: list[Episode], updated: Episode) -> list[Episode]:
    return [updated if e.id == updated.id else e for e in episodes]


@app.callback()
def _root() -> None:
    """Kurtlar Vadisi transkript pipeline'ı. Aşamalar: catalog → fetch → asr → diarize → align."""


@app.command()
def catalog() -> None:
    """İki resmi playlist'i tarayıp data/public/episodes.json üretir; eksik/çift bölümleri raporlar."""
    entries: dict[str, list[dict]] = {}
    for series, url in catalog_mod.PLAYLISTS:
        items = catalog_mod.fetch_playlist(url)
        entries.setdefault(series, []).extend(items)
        console.print(f"[bold]{series}[/] {url.split('=')[-1]}: {len(items)} video")
    extra = catalog_mod.load_extra()
    if extra:
        console.print(f"[bold]extra[/] {catalog_mod.extra_file().name}: {len(extra)} bölüm")
    episodes, warnings = catalog_mod.build_catalog(entries, extra=extra)
    catalog_mod.save_episodes(episodes)
    for w in warnings:
        console.print(f"[yellow]uyarı[/] {w}")
    missing = catalog_mod.gaps(episodes)
    if missing:
        console.print(f"[red]eksik {len(missing)} bölüm:[/] {', '.join(missing)}")
    console.print(f"[green]{len(episodes)} bölüm yazıldı[/] → {catalog_mod.episodes_file()}")


@app.command()
def fetch(
    ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt,
    sleep: float = typer.Option(5.0, help="İndirmeler arası bekleme (sn), YouTube throttling'e karşı"),
) -> None:
    """Sesi (yalnız ses) ve otomatik TR altyazıyı indirir; parça sürelerini ölçüp episodes.json'ı günceller."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        if state.is_done(e.key, "fetch") and not force:
            console.print(f"[dim]{e.id} fetch atlandı (bitmiş)[/]")
            continue
        try:
            updated = fetch_mod.fetch_episode(e, sleep=sleep)
        except Exception as exc:  # noqa: BLE001 — keep the batch going, record the failure
            state.record_error(e.key, "fetch", str(exc))
            console.print(f"[red]{e.id} fetch hata:[/] {exc}")
            continue
        episodes = _replace_episode(episodes, updated)
        catalog_mod.save_episodes(episodes)
        total = sum(p.duration_sec or 0 for p in updated.parts)
        state.mark_done(e.key, "fetch", parts=len(updated.parts), duration_sec=total)
        console.print(f"[green]{e.id}[/] {len(updated.parts)} parça, {total/60:.1f} dk")


@app.command()
def asr(
    ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt,
    model: str = typer.Option("large-v3", help="faster-whisper modeli: large-v3 | large-v3-turbo"),
    batch_size: int = typer.Option(16, help="Batched inference boyutu (VRAM'e göre)"),
) -> None:
    """Sesi faster-whisper ile kelime zamanlı transkript eder → data/private/asr/."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        if state.is_done(e.key, "asr") and not force:
            console.print(f"[dim]{e.id} asr atlandı (bitmiş)[/]")
            continue
        if not state.is_done(e.key, "fetch"):
            console.print(f"[yellow]{e.id} asr atlandı: önce fetch[/]")
            continue
        try:
            total_dur = total_elapsed = 0.0
            for i, _ in enumerate(e.parts, start=1):
                result = asr_mod.transcribe(audio_path(e.key, i), model_name=model, batch_size=batch_size)
                asr_path(e.key, i).write_text(result.model_dump_json(), encoding="utf-8")
                total_dur += result.audio_duration
                total_elapsed += result.elapsed
        except Exception as exc:  # noqa: BLE001
            state.record_error(e.key, "asr", str(exc))
            console.print(f"[red]{e.id} asr hata:[/] {exc}")
            continue
        rtf = total_elapsed / total_dur if total_dur else 0.0
        state.mark_done(e.key, "asr", model=model, rtf=round(rtf, 4), elapsed=round(total_elapsed, 1))
        console.print(f"[green]{e.id}[/] asr {total_elapsed/60:.1f} dk, RTF {rtf:.3f} ({1/rtf if rtf else 0:.0f}× gerçek zaman)")


@app.command()
def diarize(
    ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt,
) -> None:
    """pyannote ile konuşmacı ayrıştırma + konuşmacı embedding'leri → data/private/diar/."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        if state.is_done(e.key, "diarize") and not force:
            console.print(f"[dim]{e.id} diarize atlandı (bitmiş)[/]")
            continue
        if not state.is_done(e.key, "fetch"):
            console.print(f"[yellow]{e.id} diarize atlandı: önce fetch[/]")
            continue
        try:
            elapsed = 0.0
            speakers = 0
            for i, _ in enumerate(e.parts, start=1):
                result = diarize_mod.diarize(audio_path(e.key, i))
                diar_path(e.key, i).write_text(result.model_dump_json(), encoding="utf-8")
                elapsed += result.elapsed
                speakers += len({t.speaker for t in result.turns})
        except Exception as exc:  # noqa: BLE001
            state.record_error(e.key, "diarize", str(exc))
            console.print(f"[red]{e.id} diarize hata:[/] {exc}")
            continue
        dur = (state.stage_meta(e.key, "fetch") or {}).get("duration_sec") or 0.0
        rtf = elapsed / dur if dur else 0.0
        state.mark_done(e.key, "diarize", rtf=round(rtf, 4), elapsed=round(elapsed, 1), speakers=speakers)
        console.print(f"[green]{e.id}[/] diarize {elapsed/60:.1f} dk, RTF {rtf:.3f}, {speakers} konuşmacı")


@app.command()
def align(
    ep: list[str] = EpOpt, all_: bool = AllOpt, series: str | None = SeriesOpt, force: bool = ForceOpt,
) -> None:
    """ASR kelimelerini konuşmacı turn'leriyle birleştirip utterance JSONL üretir."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        if state.is_done(e.key, "align") and not force:
            console.print(f"[dim]{e.id} align atlandı (bitmiş)[/]")
            continue
        if not (state.is_done(e.key, "asr") and state.is_done(e.key, "diarize")):
            console.print(f"[yellow]{e.id} align atlandı: önce asr + diarize[/]")
            continue
        try:
            utts = align_mod.align_episode(e)
            with utterances_path(e.key).open("w", encoding="utf-8") as fh:
                for u in utts:
                    fh.write(u.model_dump_json() + "
")
        except Exception as exc:  # noqa: BLE001
            state.record_error(e.key, "align", str(exc))
            console.print(f"[red]{e.id} align hata:[/] {exc}")
            continue
        speakers = len({u.speaker for u in utts})
        state.mark_done(e.key, "align", utterances=len(utts), speakers=speakers)
        console.print(f"[green]{e.id}[/] {len(utts)} utterance, {speakers} konuşmacı")


if __name__ == "__main__":
    app()
