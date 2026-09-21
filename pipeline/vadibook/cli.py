"""vadibook CLI. Each stage command is idempotent per episode; see `vadibook run`."""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console

from vadibook import catalog as catalog_mod
from vadibook.paths import REPO_ROOT

load_dotenv(REPO_ROOT / "pipeline" / ".env")

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Kurtlar Vadisi transkript pipeline'ı")
console = Console()


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


if __name__ == "__main__":
    app()
