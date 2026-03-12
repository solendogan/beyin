"""Brainpack CLI — build and query commands."""
from pathlib import Path

import typer

from brainpack.config import load_config
from brainpack.chunker import chunk_text
from brainpack.embedder import load_model
from brainpack.ingester import fetch_article
from brainpack.pack_state import (
    check_model_provenance,
    is_processed,
    load_state,
    mark_failed,
    mark_processed,
    save_state,
)
from brainpack.store import embed_and_store, get_collection
from brainpack.query import run_query

app = typer.Typer(help="Brainpack — turn creator content into queryable expert memory")

_PACKS_DIR = Path.home() / ".brainpacks"


def _resolve_pack_dir(pack: str) -> Path:
    """Resolve pack name to directory under ~/.brainpacks/."""
    pack_dir = _PACKS_DIR / pack
    if not pack_dir.exists():
        typer.echo(f"Error: Pack '{pack}' not found at {pack_dir}", err=True)
        typer.echo(
            f"Create the directory and add a pack.yaml, or run: mkdir -p {pack_dir}",
            err=True,
        )
        raise typer.Exit(code=1)
    return pack_dir


@app.command()
def build(
    pack: str = typer.Argument(..., help="Pack name (directory under ~/.brainpacks/)")
):
    """Build or incrementally update a pack from its pack.yaml sources."""
    pack_dir = _resolve_pack_dir(pack)
    config = load_config(pack_dir)
    state = load_state(pack_dir)

    # SAF-01: enforce model provenance before any ChromaDB write
    check_model_provenance(state, config.embedding_model, pack_name=config.name)
    save_state(pack_dir, state)  # persist model registration on first build

    model = load_model(config.embedding_model)
    collection = get_collection(pack_dir, config.name)

    total_new = 0
    for url in config.sources:
        if is_processed(state, url):
            typer.echo(f"  [skip] {url}")
            continue

        typer.echo(f"  [fetch] {url}")
        result = fetch_article(url)
        if result is None:
            typer.echo(f"  [warn] Could not extract text from {url} — skipping", err=True)
            mark_failed(state, url, reason="trafilatura extraction returned None")
            save_state(pack_dir, state)
            continue

        text, title = result
        typer.echo(f"  [chunk] {title}")
        chunks = chunk_text(text)

        metadatas = [{"url": url, "title": title} for _ in chunks]
        new_count = embed_and_store(collection, model, chunks, metadatas, url=url)
        total_new += new_count

        mark_processed(state, url, title)
        save_state(pack_dir, state)
        typer.echo(f"  [done]  {title} — {new_count} new chunks")

    typer.echo(f"\nBuild complete. {total_new} new chunks indexed.")


@app.command()
def query(
    pack: str = typer.Argument(..., help="Pack name to query"),
    question: str = typer.Argument(..., help="Question to answer"),
):
    """Query a pack and receive a cited LLM answer."""
    pack_dir = _resolve_pack_dir(pack)
    config = load_config(pack_dir)
    model = load_model(config.embedding_model)
    collection = get_collection(pack_dir, config.name)

    result = run_query(
        question=question,
        collection=collection,
        model=model,
        llm_provider=config.llm,
    )

    typer.echo(result["answer"])
    typer.echo("\nSources:")
    for i, source in enumerate(result["sources"], start=1):
        title = source.get("title", "Unknown")
        url = source.get("url", "")
        typer.echo(f"  [{i}] {title} — {url}")


if __name__ == "__main__":
    app()
