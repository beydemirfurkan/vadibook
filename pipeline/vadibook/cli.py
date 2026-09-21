"""vadibook CLI. Each stage is idempotent per episode; `run` chains them and resumes after interruption."""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from vadibook import align as align_mod
from vadibook import asr as asr_mod
from vadibook import build as build_mod
from vadibook import catalog as catalog_mod
from vadibook import diarize as diarize_mod
from vadibook import fetch as fetch_mod
from vadibook import state
from vadibook.models import Episode
from vadibook.paths import REPO_ROOT, asr_path, audio_path, diar_path, utterances_path

load_dotenv(REPO_ROOT / "pipeline" / ".env")

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Kurtlar Vadisi transkript pipeline'ı")
console = Console()

STAGES: tuple[str, ...] = ("fetch", "asr", "diarize", "align")

EpOpt = typer.Option([], "--ep", help="Bölüm id'si, tekrarlanabilir: --ep pusu/17 --ep kv/3")
AllOpt = typer.Option(False, "--all", help="Katalogdaki tüm bölümler")
SeriesOpt = typer.Option(None, "--series", help="Sadece bu seri: kv | pusu")
ForceOpt = typer.Option(False, "--force", help="Bitmiş aşamayı yeniden çalıştır")
ModelOpt = typer.Option("large-v3-turbo", "--model", help="faster-whisper modeli: large-v3-turbo (varsayılan) | large-v3")
BatchOpt = typer.Option(16, "--batch-size", help="Batched inference boyutu (VRAM'e göre)")
SleepOpt = typer.Option(5.0, "--sleep", help="İndirmeler arası bekleme (sn), YouTube throttling'e karşı")


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


def parse_stages(spec: str | None) -> tuple[str, ...]:
    if not spec:
        return STAGES
    stages = tuple(s.strip() for s in spec.split(",") if s.strip())
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        raise typer.BadParameter(f"bilinmeyen aşama: {', '.join(unknown)} (geçerli: {', '.join(STAGES)})")
    return stages


def _replace_episode(episodes: list[Episode], updated: Episode) -> list[Episode]:
    return [updated if e.id == updated.id else e for e in episodes]


def all_settled(episodes: list[Episode], stages: tuple[str, ...]) -> bool:
    """True when every selected episode has each wanted stage either done or recorded as an error."""
    for e in episodes:
        st = state.load(e.key)
        for stage in stages:
            if stage not in st["stages"] and stage not in st["errors"]:
                return False
    return True


# --- per-episode stage bodies (shared by the stage commands and `run`) -------------------------


def _fetch_one(e: Episode, episodes: list[Episode], sleep: float) -> list[Episode]:
    updated = fetch_mod.fetch_episode(e, sleep=sleep)
    episodes = _replace_episode(episodes, updated)
    catalog_mod.save_episodes(episodes)
    total = sum(p.duration_sec or 0 for p in updated.parts)
    state.mark_done(e.key, "fetch", parts=len(updated.parts), duration_sec=total)
    console.print(f"[green]{e.id}[/] {len(updated.parts)} parça, {total / 60:.1f} dk")
    return episodes


def _asr_one(e: Episode, model: str, batch_size: int) -> None:
    total_dur = total_elapsed = 0.0
    for i, _ in enumerate(e.parts, start=1):
        result = asr_mod.transcribe(audio_path(e.key, i), model_name=model, batch_size=batch_size)
        asr_path(e.key, i).write_text(result.model_dump_json(), encoding="utf-8")
        total_dur += result.audio_duration
        total_elapsed += result.elapsed
    rtf = total_elapsed / total_dur if total_dur else 0.0
    state.mark_done(e.key, "asr", model=model, rtf=round(rtf, 4), elapsed=round(total_elapsed, 1))
    speed = f"{1 / rtf:.0f}" if rtf else "?"
    console.print(f"[green]{e.id}[/] asr {total_elapsed / 60:.1f} dk, RTF {rtf:.3f} ({speed}× gerçek zaman)")


def _diarize_one(e: Episode) -> None:
    elapsed = 0.0
    speakers = 0
    for i, _ in enumerate(e.parts, start=1):
        result = diarize_mod.diarize(audio_path(e.key, i))
        diar_path(e.key, i).write_text(result.model_dump_json(), encoding="utf-8")
        elapsed += result.elapsed
        speakers += len({t.speaker for t in result.turns})
    dur = (state.stage_meta(e.key, "fetch") or {}).get("duration_sec") or 0.0
    rtf = elapsed / dur if dur else 0.0
    state.mark_done(e.key, "diarize", rtf=round(rtf, 4), elapsed=round(elapsed, 1), speakers=speakers)
    console.print(f"[green]{e.id}[/] diarize {elapsed / 60:.1f} dk, RTF {rtf:.3f}, {speakers} konuşmacı")


def _align_one(e: Episode) -> None:
    utts = align_mod.align_episode(e)
    with utterances_path(e.key).open("w", encoding="utf-8") as fh:
        for u in utts:
            fh.write(u.model_dump_json() + "\n")
    speakers = len({u.speaker for u in utts})
    state.mark_done(e.key, "align", utterances=len(utts), speakers=speakers)
    console.print(f"[green]{e.id}[/] {len(utts)} utterance, {speakers} konuşmacı")


_PREREQ = {"fetch": (), "asr": ("fetch",), "diarize": ("fetch",), "align": ("asr", "diarize")}


def _run_stage(
    stage: str,
    e: Episode,
    episodes: list[Episode],
    *,
    force: bool,
    model: str,
    batch_size: int,
    sleep: float,
) -> list[Episode]:
    """Run one stage for one episode with skip/prereq/error bookkeeping. Returns possibly-updated catalog."""
    if state.is_done(e.key, stage) and not force:
        console.print(f"[dim]{e.id} {stage} atlandı (bitmiş)[/]")
        return episodes
    missing = [p for p in _PREREQ[stage] if not state.is_done(e.key, p)]
    if missing:
        console.print(f"[yellow]{e.id} {stage} atlandı: önce {', '.join(missing)}[/]")
        return episodes
    try:
        if stage == "fetch":
            return _fetch_one(e, episodes, sleep)
        if stage == "asr":
            _asr_one(e, model, batch_size)
        elif stage == "diarize":
            _diarize_one(e)
        elif stage == "align":
            _align_one(e)
    except Exception as exc:  # noqa: BLE001 — record and keep the batch going
        state.record_error(e.key, stage, str(exc))
        console.print(f"[red]{e.id} {stage} hata:[/] {exc}")
    return episodes


# --- commands ---------------------------------------------------------------------------------


@app.callback()
def _root() -> None:
    """Kurtlar Vadisi transkript pipeline'ı. Aşamalar: catalog → fetch → asr → diarize → align."""


@app.command()
def catalog() -> None:
    """Resmi playlist'leri tarayıp data/public/episodes.json üretir; eksik/çift bölümleri raporlar."""
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
    ep: list[str] = EpOpt,
    all_: bool = AllOpt,
    series: str | None = SeriesOpt,
    force: bool = ForceOpt,
    sleep: float = SleepOpt,
) -> None:
    """Sesi (yalnız ses) ve otomatik TR altyazıyı indirir; parça sürelerini ölçüp episodes.json'ı günceller."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        episodes = _run_stage("fetch", e, episodes, force=force, model="", batch_size=0, sleep=sleep)


@app.command()
def asr(
    ep: list[str] = EpOpt,
    all_: bool = AllOpt,
    series: str | None = SeriesOpt,
    force: bool = ForceOpt,
    model: str = ModelOpt,
    batch_size: int = BatchOpt,
) -> None:
    """Sesi faster-whisper ile kelime zamanlı transkript eder → data/private/asr/."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        _run_stage("asr", e, episodes, force=force, model=model, batch_size=batch_size, sleep=0)


@app.command()
def diarize(
    ep: list[str] = EpOpt,
    all_: bool = AllOpt,
    series: str | None = SeriesOpt,
    force: bool = ForceOpt,
) -> None:
    """pyannote ile konuşmacı ayrıştırma + konuşmacı embedding'leri → data/private/diar/."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        _run_stage("diarize", e, episodes, force=force, model="", batch_size=0, sleep=0)


@app.command()
def align(
    ep: list[str] = EpOpt,
    all_: bool = AllOpt,
    series: str | None = SeriesOpt,
    force: bool = ForceOpt,
) -> None:
    """ASR kelimelerini konuşmacı turn'leriyle birleştirip utterance JSONL üretir."""
    episodes = catalog_mod.load_episodes()
    for e in select_episodes(episodes, ep, all_, series):
        _run_stage("align", e, episodes, force=force, model="", batch_size=0, sleep=0)


@app.command()
def run(
    ep: list[str] = EpOpt,
    all_: bool = AllOpt,
    series: str | None = SeriesOpt,
    force: bool = ForceOpt,
    stages: str | None = typer.Option(
        None, "--stages", help="Virgülle: fetch,asr,diarize,align (varsayılan hepsi)"
    ),
    model: str = ModelOpt,
    batch_size: int = BatchOpt,
    sleep: float = SleepOpt,
    repeat: float | None = typer.Option(
        None, "--repeat", help="Saniye: ön koşulu bekleyen bölümler için bu aralıkla yeniden tara, hepsi bitene kadar"
    ),
) -> None:
    """Seçili bölümler için aşamaları sırayla çalıştırır; kesilirse `state/` sayesinde kaldığı yerden devam eder."""
    import time

    wanted = parse_stages(stages)
    while True:
        episodes = catalog_mod.load_episodes()  # re-read: a parallel `fetch` run may have updated durations
        selected = select_episodes(episodes, ep, all_, series)
        for e in selected:
            for stage in wanted:
                episodes = _run_stage(
                    stage, e, episodes, force=force, model=model, batch_size=batch_size, sleep=sleep
                )
        force = False  # a forced re-run applies to the first pass only
        if repeat is None or all_settled(selected, wanted):
            break
        console.print(f"[dim]bekleyen bölümler var, {repeat:.0f} sn sonra yeniden taranacak[/]")
        time.sleep(repeat)


@app.command()
def build(
    push: bool = typer.Option(False, "--push", help="Meilisearch'e de gönder"),
    meili_url: str = typer.Option("http://localhost:7700", "--meili-url", envvar="MEILI_URL"),
    meili_key: str = typer.Option("", "--meili-key", envvar="MEILI_MASTER_KEY"),
) -> None:
    """align'ı bitmiş bölümleri SQLite'a yazar; --push ile Meilisearch indeksini günceller."""
    import sqlite3

    episodes = catalog_mod.load_episodes()
    stats = build_mod.build_sqlite(episodes)
    console.print(
        f"[green]sqlite[/] {stats['episodes']} bölüm, {stats['utterances']} utterance → {build_mod.sqlite_path()}"
    )
    if push:
        conn = sqlite3.connect(build_mod.sqlite_path())
        n = build_mod.push_meili(meili_url, meili_key, build_mod.meili_docs(conn))
        console.print(f"[green]meilisearch[/] {n} doküman gönderildi → {meili_url}/indexes/{build_mod.MEILI_INDEX}")


@app.command()
def status(series: str | None = SeriesOpt) -> None:
    """Bölüm × aşama tablosu (RTF = işlem süresi / ses süresi)."""
    episodes = catalog_mod.load_episodes()
    if series:
        episodes = [e for e in episodes if e.series == series]
    table = Table(title="vadibook durum")
    for col in ("bölüm", "parça", "dk", "fetch", "asr (rtf)", "diarize (rtf)", "align (utt)", "hata"):
        table.add_column(col)
    done_counts = dict.fromkeys(STAGES, 0)
    for e in episodes:
        st = state.load(e.key)
        stages = st["stages"]
        for s in STAGES:
            done_counts[s] += s in stages
        dur = (stages.get("fetch") or {}).get("duration_sec")
        table.add_row(
            e.id,
            str(len(e.parts)),
            f"{dur / 60:.0f}" if dur else "",
            "✓" if "fetch" in stages else "",
            f"{stages['asr'].get('rtf', '')}" if "asr" in stages else "",
            f"{stages['diarize'].get('rtf', '')}" if "diarize" in stages else "",
            f"{stages['align'].get('utterances', '')}" if "align" in stages else "",
            "; ".join(f"{k}: {v['message'][:40]}" for k, v in st["errors"].items()),
        )
    console.print(table)
    console.print(" · ".join(f"{s}: {done_counts[s]}/{len(episodes)}" for s in STAGES))


if __name__ == "__main__":
    app()
