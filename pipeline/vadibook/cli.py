"""vadibook CLI. Each stage command is idempotent per episode; see `vadibook run`."""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console

from vadibook import catalog as catalog_mod
from vadibook import fetch as fetch_mod
from vadibook import state
from vadibook.models import Episode
from vadibook.paths import REPO_ROOT

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


if __name__ == "__main__":
    app()
