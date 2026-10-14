from __future__ import annotations

import json
import logging
from pathlib import Path

import typer

from ticketpilot.config import get_settings

app = typer.Typer(help="Ticket triage, resolution agent and inbox", no_args_is_help=True)
data_app = typer.Typer(help="Datasets", no_args_is_help=True)
app.add_typer(data_app, name="data")


@data_app.command("download")
def data_download(force: bool = typer.Option(False, help="Download again even if the file exists")) -> None:
    from ticketpilot.data import bitext

    path = bitext.download(force=force)
    typer.echo(f"{path} ({path.stat().st_size / 1e6:.1f} MB)")


@data_app.command("generate")
def data_generate(
    count: int = typer.Option(2000, help="Number of tickets"),
    seed: int = typer.Option(13),
    foreign_share: float = typer.Option(0.0, help="Share of tickets in es, fr or de"),
    output: Path = typer.Option(None, help="Output jsonl path"),
) -> None:
    from ticketpilot.data.io import write_tickets
    from ticketpilot.data.synthetic import generate_tickets

    target = output or get_settings().data_dir / "synthetic_tickets.jsonl"
    written = write_tickets(generate_tickets(count, seed, foreign_share), target)
    typer.echo(f"wrote {written} tickets to {target}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app()


if __name__ == "__main__":
    main()
