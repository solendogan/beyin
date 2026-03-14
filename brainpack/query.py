"""Query pipeline: embed question -> retrieve chunks -> cap context -> call LLM."""
import os
from typing import Any, Dict, List, Tuple

_ENC = None
OpenAI = None
DEFAULT_EVIDENCE_RESULTS = 8
ANSWER_RESULTS = 5


def _encoding():
    """Load the tokenizer lazily to keep non-query CLI startup fast."""
    global _ENC
    if _ENC is None:
        import tiktoken

        _ENC = tiktoken.get_encoding("cl100k_base")
    return _ENC


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
        t = len(_encoding().encode(chunk))
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


def _response_language_instruction(question: str, context: str) -> str:
    """Tell the model to answer in the user's language and avoid mixed-language drift."""
    lowered = f"{question}\n{context}".lower()
    turkish_hints = (
        " bir ",
        " ve ",
        " için ",
        " teşvik",
        "ş",
        "ğ",
        "ı",
        "ç",
        "ö",
        "ü",
    )
    if any(hint in lowered for hint in turkish_hints):
        return (
            "Answer in Turkish. Do not switch to English unless the user explicitly asks. "
            "Keep company names, product names, and proper nouns unchanged."
        )
    return (
        "Answer in the same language as the user's question. "
        "Do not mix languages unless the user explicitly asks for translation."
    )


def _embed_question(question: str, model) -> List[float]:
    """Embed one question and normalize the vector for ChromaDB query input."""
    import numpy as np

    q_vec_raw = model.encode(question)
    return np.array(q_vec_raw).flatten().tolist()


def _evidence_item(chunk: str, meta: Dict[str, Any], *, rank: int, distance: float | None) -> Dict[str, Any]:
    """Normalize one retrieved chunk into the shared evidence shape."""
    item = {
        "text": chunk,
        "url": meta.get("url", ""),
        "title": meta.get("title", "Unknown"),
        "rank": rank,
    }
    if distance is not None:
        item["distance"] = distance
    if meta.get("timestamp_start") is not None:
        item["timestamp_start"] = meta["timestamp_start"]
    if meta.get("timestamp_end") is not None:
        item["timestamp_end"] = meta["timestamp_end"]
    return item


def _source_from_evidence(item: Dict[str, Any]) -> Dict[str, Any]:
    """Return the answer-path source shape from one evidence item."""
    source = {
        "url": item["url"],
        "title": item["title"],
    }
    if item.get("timestamp_start") is not None:
        source["timestamp_start"] = item["timestamp_start"]
    if item.get("timestamp_end") is not None:
        source["timestamp_end"] = item["timestamp_end"]
    return source


def retrieve_evidence(
    question: str,
    collection,
    model,
    n_results: int = DEFAULT_EVIDENCE_RESULTS,
) -> List[Dict[str, Any]]:
    """Retrieve raw evidence items without calling the answer model."""
    q_embedding = _embed_question(question, model)
    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    chunks = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    return [
        _evidence_item(chunk, meta, rank=index, distance=distance)
        for index, (chunk, meta, distance) in enumerate(zip(chunks, metadatas, distances), start=1)
    ]


def run_query(
    question: str,
    collection,
    model,
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
    evidence = retrieve_evidence(question, collection, model, n_results=ANSWER_RESULTS)
    chunks = [item["text"] for item in evidence]

    # Step 3: Cap context at 3,000 tokens (QRY-05)
    chunks = _cap_context(chunks, max_tokens=3000)
    evidence = evidence[: len(chunks)]

    # Step 4: Build cited context with [N] labels (QRY-02)
    context_parts = []
    for item in evidence:
        source_label = _source_label(_source_from_evidence(item), index=item["rank"])
        chunk = item["text"]
        context_parts.append(f"{source_label}\n{chunk}")
    context = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "You are a helpful assistant. Answer the user's question using ONLY the "
        "provided context. "
        f"{_response_language_instruction(question, context)} "
        "Do not invent facts beyond the context. If the context does not contain "
        "enough information to answer, say so clearly."
    )
    history_block = _conversation_history_block(history)
    history_prefix = f"{history_block}\n\n" if history_block else ""
    user_message = f"{history_prefix}Context:\n{context}\n\nQuestion: {question}"

    # Step 5: Call LLM (QRY-03, QRY-04)
    base_url, api_key = _provider_settings(llm_provider)
    global OpenAI
    if OpenAI is None:
        from openai import OpenAI as _OpenAI

        OpenAI = _OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    answer = response.choices[0].message.content

    return {"answer": answer, "sources": [_source_from_evidence(item) for item in evidence]}
