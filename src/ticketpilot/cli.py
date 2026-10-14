from __future__ import annotations

import json
import logging
from pathlib import Path

import typer

from ticketpilot.config import get_settings

app = typer.Typer(help="Ticket triage, resolution agent and inbox", no_args_is_help=True)
data_app = typer.Typer(help="Datasets", no_args_is_help=True)
triage_app = typer.Typer(help="Triage models", no_args_is_help=True)
kb_app = typer.Typer(help="Knowledge base", no_args_is_help=True)
app.add_typer(data_app, name="data")
app.add_typer(triage_app, name="triage")
app.add_typer(kb_app, name="kb")


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


@triage_app.command("train")
def triage_train(
    task: str = typer.Option("synthetic_intent", help="bitext_intent, synthetic_intent or synthetic_priority"),
    kind: str = typer.Option("baseline", help="baseline or transformer"),
    epochs: int = typer.Option(3),
) -> None:
    from ticketpilot.triage.tasks import TASKS
    from ticketpilot.triage.train import train_and_save

    if task not in TASKS:
        raise typer.BadParameter(f"unknown task {task}, choose from {', '.join(TASKS)}")
    path = train_and_save(task, kind, get_settings().models_dir, epochs)
    typer.echo(f"saved {kind} model for {task} to {path}")


@triage_app.command("predict")
def triage_predict(text: str = typer.Argument(..., help="Ticket text"), email: str = "customer@example.com") -> None:
    from ticketpilot.data.schemas import Ticket
    from ticketpilot.triage.pipeline import load_pipeline

    pipeline = load_pipeline(get_settings().models_dir)
    result = pipeline.analyze(Ticket(ticket_id="cli", subject="", body=text, from_email=email))
    typer.echo(json.dumps(result.to_dict(), indent=2))


@kb_app.command("search")
def kb_search(
    query: str = typer.Argument(...),
    k: int = typer.Option(3),
    mode: str = typer.Option("hybrid_rerank", help="bm25, dense, hybrid or hybrid_rerank"),
) -> None:
    from ticketpilot.embeddings import get_embedder
    from ticketpilot.kb.rerank import CrossEncoderReranker
    from ticketpilot.kb.retriever import HybridRetriever

    settings = get_settings()
    retriever = HybridRetriever.from_directory(settings.kb_dir, get_embedder(settings.embedder), CrossEncoderReranker())
    for hit in retriever.search(query, k=k, mode=mode):
        typer.echo(f"{hit.score:8.3f}  {hit.article_id:32s} {hit.chunk.heading}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app()


if __name__ == "__main__":
    main()
