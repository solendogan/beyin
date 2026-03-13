"""Query pipeline: embed question -> retrieve chunks -> cap context -> call LLM."""
import os
from typing import Any, Dict, List, Tuple

import numpy as np
import tiktoken
from openai import OpenAI
from sentence_transformers import SentenceTransformer

_enc = tiktoken.get_encoding("cl100k_base")


def _provider_settings(provider: str) -> Tuple[str, str]:
    """Return (base_url, api_key) for the given LLM provider."""
    if provider == "ollama":
        return "http://localhost:11434/v1", "ollama"
    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        return "https://api.openai.com/v1", api_key
    elif provider == "anthropic":
        raise NotImplementedError(
            "Anthropic is not supported in this phase. "
            "Update pack.yaml to use llm: ollama or llm: openai."
        )
    raise ValueError(f"Unknown LLM provider: '{provider}'. Valid options: ollama, openai.")


def _cap_context(chunks: List[str], max_tokens: int = 3000) -> List[str]:
    """
    Return the largest prefix of chunks whose cumulative token count <= max_tokens.

    Chunks are taken in order (highest relevance first, per ChromaDB ranking).
    A chunk that would push the total over the limit is dropped — not truncated.
    """
    kept, total = [], 0
    for chunk in chunks:
        t = len(_enc.encode(chunk))
        if total + t > max_tokens:
            break
        kept.append(chunk)
        total += t
    return kept


def _format_timestamp(seconds: float) -> str:
    """Render a second count as MM:SS or HH:MM:SS."""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _source_label(meta: Dict[str, Any], index: int | None = None) -> str:
    """Format a human-readable source label, including timestamps when present."""
    prefix = f"[{index}] " if index is not None else ""
    label = f"{prefix}{meta.get('title', 'Unknown')} — {meta.get('url', '')}"
    start = meta.get("timestamp_start")
    end = meta.get("timestamp_end")
    if start is not None and end is not None:
        label = f"{label} ({_format_timestamp(start)}-{_format_timestamp(end)})"
    return label


def _conversation_history_block(history: List[Dict[str, str]] | None) -> str:
    """Render prior chat turns for session-local conversational context."""
    if not history:
        return ""

    lines = ["Conversation so far:"]
    for turn in history:
        lines.append(f"User: {turn['question']}")
        lines.append(f"Assistant: {turn['answer']}")
    return "\n".join(lines)


def run_query(
    question: str,
    collection,
    model: SentenceTransformer,
    llm_provider: str = "ollama",
    llm_model: str = "llama3.2",
    history: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """
    Run a full RAG query against the collection.

    Steps:
    1. Embed the question using the same model used at build time
    2. Retrieve top-5 chunks from ChromaDB (QRY-06)
    3. Cap context at 3,000 tokens (QRY-05)
    4. Format a cited context prompt with [N] labels
    5. Call LLM via openai client (QRY-03, QRY-04)
    6. Return {"answer": str, "sources": List[Dict]}

    Returns sources as the metadata dicts from ChromaDB — each contains at
    minimum {"url": ..., "title": ...} as stored by embed_and_store.
    """
    # Step 1: Embed question (single vector)
    # model.encode on a single string may return 1D or 2D depending on backend.
    # Flatten to 1D then convert to list for ChromaDB compatibility.
    q_vec_raw = model.encode(question)
    q_embedding = np.array(q_vec_raw).flatten().tolist()

    # Step 2: Retrieve top-5 chunks (QRY-06)
    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=5,
        include=["documents", "metadatas", "distances"],
    )
    chunks = results["documents"][0]
    metadatas = results["metadatas"][0]

    # Step 3: Cap context at 3,000 tokens (QRY-05)
    chunks = _cap_context(chunks, max_tokens=3000)
    metadatas = metadatas[: len(chunks)]

    # Step 4: Build cited context with [N] labels (QRY-02)
    context_parts = []
    for i, (chunk, meta) in enumerate(zip(chunks, metadatas)):
        source_label = _source_label(meta, index=i + 1)
        context_parts.append(f"{source_label}\n{chunk}")
    context = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "You are a helpful assistant. Answer the user's question using ONLY the "
        "provided context. After your answer, list the sources you used as numbered "
        "citations matching the [N] labels in the context. If the context does not "
        "contain enough information to answer, say so clearly."
    )
    history_block = _conversation_history_block(history)
    history_prefix = f"{history_block}\n\n" if history_block else ""
    user_message = f"{history_prefix}Context:\n{context}\n\nQuestion: {question}"

    # Step 5: Call LLM (QRY-03, QRY-04)
    base_url, api_key = _provider_settings(llm_provider)
    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    answer = response.choices[0].message.content

    return {"answer": answer, "sources": metadatas}
