"""ChromaDB vector storage — PersistentClient, one collection per pack."""
from pathlib import Path
from typing import Any, Dict, List

import chromadb

from beyin.embedder import embed_chunks


def get_collection(pack_dir: Path, pack_name: str):
    """
    Get or create a ChromaDB collection for this pack.

    Uses PersistentClient backed by SQLite under pack_dir/chroma/.
    Safe to call repeatedly — get_or_create_collection is idempotent.

    IMPORTANT: Use chromadb.PersistentClient(path=...), NOT the old
    chromadb.Client(Settings(chroma_db_impl=...)) API (removed in 1.x).
    """
    chroma_path = pack_dir / "chroma"
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    return client.get_or_create_collection(name=pack_name)


def embed_and_store(
    collection,
    model,
    chunks: List[str],
    metadatas: List[Dict[str, Any]],
    url: str,
) -> int:
    """
    Embed chunks and store them in the collection with metadata.

    Chunk IDs are deterministic: "{url}::chunk::{i}" — allows incremental
    builds to detect already-stored chunks without re-embedding.

    Returns the number of NEW chunks stored (0 if all already exist).

    Handles the incremental case by checking existing IDs first to avoid
    ChromaDB's duplicate-ID error on collection.add().
    """
    if not chunks:
        return 0

    ids = [f"{url}::chunk::{i}" for i in range(len(chunks))]

    # Check which IDs already exist in the collection
    existing_result = collection.get(ids=ids)
    existing_ids = set(existing_result["ids"])

    new_indices = [i for i, cid in enumerate(ids) if cid not in existing_ids]
    if not new_indices:
        return 0  # All chunks already stored — incremental skip

    new_chunks = [chunks[i] for i in new_indices]
    new_ids = [ids[i] for i in new_indices]
    new_meta = [metadatas[i] for i in new_indices]

    embeddings = embed_chunks(model, new_chunks)

    collection.add(
        ids=new_ids,
        embeddings=embeddings,
        documents=new_chunks,
        metadatas=new_meta,
    )
    return len(new_indices)
