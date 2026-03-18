#!/usr/bin/env python3
"""
Brainpack Retrieval Benchmark
=============================
Measures Hit Rate@k, MRR, and latency against a golden dataset.
Results are saved to benchmarks/results/<label>.md

Usage:
    uv run python benchmarks/retrieval_benchmark.py
    uv run python benchmarks/retrieval_benchmark.py --pack armag-2 --label baseline
    uv run python benchmarks/retrieval_benchmark.py --label larger-n --n-results 20
    uv run python benchmarks/retrieval_benchmark.py --label rerank \\
        --reranker cross-encoder/ms-marco-MiniLM-L-6-v2 --n-candidates 20
    uv run python benchmarks/retrieval_benchmark.py --label rerank-bge \\
        --reranker BAAI/bge-reranker-base --n-candidates 20
"""

import argparse
import sys
import time
import statistics
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from brainpack.query import retrieve_evidence
from brainpack.embedder import load_model
from brainpack.store import get_collection
from brainpack.config import load_config

# ── Golden dataset ─────────────────────────────────────────────────────────────
# Each entry: question, expected source URL, episode label, language
# Questions designed to cover direct keyword matches, semantic queries,
# and cross-language queries to stress-test retrieval quality.

GOLDEN_DATASET = [
    # ── ChatGPT, AI, Prompt Engineering ───────────────────────────────────────
    {
        "question": "ChatGPT ve prompt engineering hakkında neler konuşuldu?",
        "expected_url": "https://www.youtube.com/watch?v=Il_8LUGhDys",
        "episode": "ChatGPT, AI, Prompt Engineering",
        "lang": "tr",
    },
    {
        "question": "Yapay zeka ile kod yazmak ve öğrencilere kullandırmak",
        "expected_url": "https://www.youtube.com/watch?v=Il_8LUGhDys",
        "episode": "ChatGPT, AI, Prompt Engineering",
        "lang": "tr",
    },
    {
        "question": "AI code generation and teaching students",
        "expected_url": "https://www.youtube.com/watch?v=Il_8LUGhDys",
        "episode": "ChatGPT, AI, Prompt Engineering",
        "lang": "en",
    },

    # ── Elektronik ve Müzik Hobileri ──────────────────────────────────────────
    {
        "question": "elektrik gitar pedal ve elektronik hobiler",
        "expected_url": "https://www.youtube.com/watch?v=dtYN2GWS37c",
        "episode": "Elektronik ve Müzik Hobileri",
        "lang": "tr",
    },
    {
        "question": "müzik ekipmanları ve ses düzeni",
        "expected_url": "https://www.youtube.com/watch?v=dtYN2GWS37c",
        "episode": "Elektronik ve Müzik Hobileri",
        "lang": "tr",
    },
    {
        "question": "guitar pedals and electronics hobby",
        "expected_url": "https://www.youtube.com/watch?v=dtYN2GWS37c",
        "episode": "Elektronik ve Müzik Hobileri",
        "lang": "en",
    },

    # ── JSDoc, Clean/Hexagonal Architecture ───────────────────────────────────
    {
        "question": "yazılım mimarisi hexagonal onion clean architecture",
        "expected_url": "https://www.youtube.com/watch?v=RZOSR7XLIfI",
        "episode": "JSDoc, Architecture Patterns",
        "lang": "tr",
    },
    {
        "question": "JSDoc kullanımı ve faydaları",
        "expected_url": "https://www.youtube.com/watch?v=RZOSR7XLIfI",
        "episode": "JSDoc, Architecture Patterns",
        "lang": "tr",
    },
    {
        "question": "software architecture layered hexagonal design patterns",
        "expected_url": "https://www.youtube.com/watch?v=RZOSR7XLIfI",
        "episode": "JSDoc, Architecture Patterns",
        "lang": "en",
    },

    # ── ADHD, Kişisel Gelişim ─────────────────────────────────────────────────
    {
        "question": "ADHD ile çalışmak ve planlı yaşam",
        "expected_url": "https://www.youtube.com/watch?v=A_8qf7CEHOw",
        "episode": "ADHD, Kişisel Gelişim",
        "lang": "tr",
    },
    {
        "question": "uyku düzeni ve kişisel verimlilik",
        "expected_url": "https://www.youtube.com/watch?v=A_8qf7CEHOw",
        "episode": "ADHD, Kişisel Gelişim",
        "lang": "tr",
    },
    {
        "question": "ADHD productivity and personal development in software",
        "expected_url": "https://www.youtube.com/watch?v=A_8qf7CEHOw",
        "episode": "ADHD, Kişisel Gelişim",
        "lang": "en",
    },

    # ── Nasıl Kütüphane Yazılır, Composition API ──────────────────────────────
    {
        "question": "Vue Composition API ve Options API karşılaştırması",
        "expected_url": "https://www.youtube.com/watch?v=rGtGx7IsYCU",
        "episode": "Kütüphane Yazımı, Composition API",
        "lang": "tr",
    },
    {
        "question": "JavaScript kütüphanesi nasıl yazılır",
        "expected_url": "https://www.youtube.com/watch?v=rGtGx7IsYCU",
        "episode": "Kütüphane Yazımı, Composition API",
        "lang": "tr",
    },
    {
        "question": "how to build a JavaScript library composition vs options api",
        "expected_url": "https://www.youtube.com/watch?v=rGtGx7IsYCU",
        "episode": "Kütüphane Yazımı, Composition API",
        "lang": "en",
    },

    # ── Sabancı, Global Ekonomi, Kadın Yazılımcılar ───────────────────────────
    {
        "question": "global ekonomi ve para birimleri arasındaki fark",
        "expected_url": "https://www.youtube.com/watch?v=re4K1Ohr-v8",
        "episode": "Sabancı, Global Ekonomi",
        "lang": "tr",
    },
    {
        "question": "Sabancı üniversitesi yazılım mühendisliği deneyimi",
        "expected_url": "https://www.youtube.com/watch?v=re4K1Ohr-v8",
        "episode": "Sabancı, Global Ekonomi",
        "lang": "tr",
    },
    {
        "question": "women in software engineering and global economy",
        "expected_url": "https://www.youtube.com/watch?v=re4K1Ohr-v8",
        "episode": "Sabancı, Global Ekonomi",
        "lang": "en",
    },

    # ── Yazılım Dolandırıcılığı, Software Testing ─────────────────────────────
    {
        "question": "yazılım sektöründe dolandırıcılık ve sahtecilik",
        "expected_url": "https://www.youtube.com/watch?v=iYxLoh3Dqfg",
        "episode": "Dolandırıcılık, Software Testing",
        "lang": "tr",
    },
    {
        "question": "software testing önemi ve test yazma",
        "expected_url": "https://www.youtube.com/watch?v=iYxLoh3Dqfg",
        "episode": "Dolandırıcılık, Software Testing",
        "lang": "tr",
    },
    {
        "question": "software scams fraud and testing practices",
        "expected_url": "https://www.youtube.com/watch?v=iYxLoh3Dqfg",
        "episode": "Dolandırıcılık, Software Testing",
        "lang": "en",
    },

    # ── İşten Çıkarmalar, Yöneticilik, Unit of Work ───────────────────────────
    {
        "question": "işten çıkarmalar neden oluyor ve nasıl önlenir",
        "expected_url": "https://www.youtube.com/watch?v=9u2EB5PrKmA",
        "episode": "İşten Çıkarmalar, Yöneticilik",
        "lang": "tr",
    },
    {
        "question": "iyi yönetici nasıl olunur liderlik",
        "expected_url": "https://www.youtube.com/watch?v=9u2EB5PrKmA",
        "episode": "İşten Çıkarmalar, Yöneticilik",
        "lang": "tr",
    },
    {
        "question": "tech layoffs and management unit of work pattern",
        "expected_url": "https://www.youtube.com/watch?v=9u2EB5PrKmA",
        "episode": "İşten Çıkarmalar, Yöneticilik",
        "lang": "en",
    },
]

RESULTS_DIR = Path(__file__).parent / "results"


def _rerank(question: str, evidence: list, reranker_model, top_k: int) -> list:
    """Rerank evidence using a cross-encoder and return top_k results."""
    pairs = [[question, e["text"]] for e in evidence]
    scores = reranker_model.predict(pairs)
    ranked = sorted(zip(scores, evidence), key=lambda x: x[0], reverse=True)
    return [e for _, e in ranked[:top_k]]


def _build_inmemory_index(collection, override_model):
    """
    Fetch all documents from ChromaDB and re-embed with override_model.
    Returns (chunks, metadatas, embeddings_matrix).
    Used to test a different bi-encoder without rebuilding the pack.
    """
    import numpy as np
    result = collection.get(include=["documents", "metadatas"])
    chunks = result["documents"]
    metadatas = result["metadatas"]
    print(f"  Re-embedding {len(chunks)} chunks with {override_model.get_sentence_embedding_dimension()}-dim model...")
    embeddings = override_model.encode(chunks, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    return chunks, metadatas, np.array(embeddings)


def _inmemory_query(question: str, chunks, metadatas, embeddings_matrix, model, n_results: int) -> list:
    """Query the in-memory index using cosine similarity."""
    import numpy as np
    q_vec = model.encode(question, normalize_embeddings=True)
    scores = embeddings_matrix @ q_vec
    top_indices = np.argsort(scores)[::-1][:n_results]
    results = []
    for rank, idx in enumerate(top_indices, start=1):
        meta = metadatas[idx]
        results.append({
            "text": chunks[idx],
            "url": meta.get("url", ""),
            "title": meta.get("title", "Unknown"),
            "rank": rank,
            "distance": float(1 - scores[idx]),
        })
    return results


def run_benchmark(
    pack: str,
    label: str,
    n_results: int = 8,
    description: str = "",
    reranker: str = "",
    n_candidates: int = 20,
    embedding_model_override: str = "",
) -> None:
    pack_dir = Path.home() / ".brainpacks" / pack
    if not pack_dir.exists():
        print(f"Pack '{pack}' not found at {pack_dir}")
        return

    config = load_config(pack_dir)
    print(f"Loading model: {config.embedding_model}")
    model = load_model(config.embedding_model)
    collection = get_collection(pack_dir, config.id)

    # Optional: override the bi-encoder with a different model (in-memory index)
    inmemory_index = None
    if embedding_model_override:
        override_model = load_model(embedding_model_override)
        inmemory_index = _build_inmemory_index(collection, override_model)
        model = override_model  # use override model for query embedding too
        print(f"  In-memory index ready ({len(inmemory_index[0])} chunks)")

    reranker_model = None
    if reranker:
        from sentence_transformers import CrossEncoder
        print(f"Loading reranker: {reranker}")
        reranker_model = CrossEncoder(reranker)

    fetch_n = n_candidates if reranker_model else n_results
    print(f"Running {len(GOLDEN_DATASET)} queries against '{pack}'...\n")

    rows = []
    latencies = []

    for item in GOLDEN_DATASET:
        t0 = time.perf_counter()
        if inmemory_index:
            chunks_idx, metas_idx, emb_matrix = inmemory_index
            evidence = _inmemory_query(item["question"], chunks_idx, metas_idx, emb_matrix, model, n_results=fetch_n)
        else:
            evidence = retrieve_evidence(item["question"], collection, model, n_results=fetch_n)
        if reranker_model:
            evidence = _rerank(item["question"], evidence, reranker_model, top_k=n_results)
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies.append(latency_ms)

        retrieved_urls = [e["url"] for e in evidence]

        try:
            rank = next(
                i + 1 for i, url in enumerate(retrieved_urls)
                if url == item["expected_url"]
            )
        except StopIteration:
            rank = None

        top_result = evidence[0] if evidence else {}

        rows.append({
            "question": item["question"],
            "episode": item["episode"],
            "lang": item["lang"],
            "expected_url": item["expected_url"],
            "rank": rank,
            "hit_1": rank == 1,
            "hit_3": rank is not None and rank <= 3,
            "hit_5": rank is not None and rank <= 5,
            "hit_8": rank is not None and rank <= 8,
            "top_distance": round(evidence[0]["distance"], 4) if evidence and "distance" in evidence[0] else None,
            "top_title": top_result.get("title", ""),
            "latency_ms": round(latency_ms, 1),
        })

        status = f"  rank={rank}" if rank else "  MISS"
        print(f"  [{item['lang']}] {item['question'][:60]:<60}{status}")

    # ── Compute metrics ────────────────────────────────────────────────────────
    n = len(rows)
    hit_1 = sum(r["hit_1"] for r in rows) / n
    hit_3 = sum(r["hit_3"] for r in rows) / n
    hit_5 = sum(r["hit_5"] for r in rows) / n
    hit_8 = sum(r["hit_8"] for r in rows) / n

    mrr = sum(1 / r["rank"] for r in rows if r["rank"] is not None) / n

    lat_mean = statistics.mean(latencies)
    lat_p95 = sorted(latencies)[int(0.95 * len(latencies))]

    # Per-language breakdown
    for lang in ("tr", "en"):
        lang_rows = [r for r in rows if r["lang"] == lang]
        if lang_rows:
            lh1 = sum(r["hit_1"] for r in lang_rows) / len(lang_rows)
            lh8 = sum(r["hit_8"] for r in lang_rows) / len(lang_rows)
            print(f"\n  [{lang}] Hit@1={lh1:.0%}  Hit@8={lh8:.0%}  ({len(lang_rows)} queries)")

    print(f"\n  Hit@1={hit_1:.0%}  Hit@3={hit_3:.0%}  Hit@5={hit_5:.0%}  Hit@8={hit_8:.0%}  MRR={mrr:.3f}")
    print(f"  Latency mean={lat_mean:.1f}ms  p95={lat_p95:.1f}ms")

    # ── Write markdown ─────────────────────────────────────────────────────────
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{label}.md"

    lines = [
        f"# Retrieval Benchmark — {label}",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        f"**Pack:** {pack}  ",
        f"**Embedding model:** {embedding_model_override or config.embedding_model}  ",
        f"**n_results:** {n_results}  ",
    ]
    if embedding_model_override:
        lines += [f"**Index embedding model:** {config.embedding_model} (index built with this)  "]
    if reranker:
        lines += [
            f"**Reranker:** {reranker}  ",
            f"**n_candidates:** {n_candidates}  ",
        ]
    lines += [
        f"**Queries:** {n} ({sum(1 for r in rows if r['lang'] == 'tr')} Turkish, {sum(1 for r in rows if r['lang'] == 'en')} English)  ",
    ]
    if description:
        lines += [f"**Description:** {description}  "]
    lines += [
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Hit Rate@1 | {hit_1:.1%} |",
        f"| Hit Rate@3 | {hit_3:.1%} |",
        f"| Hit Rate@5 | {hit_5:.1%} |",
        f"| Hit Rate@8 | {hit_8:.1%} |",
        f"| MRR@{n_results} | {mrr:.3f} |",
        f"| Latency (mean) | {lat_mean:.1f}ms |",
        f"| Latency (p95) | {lat_p95:.1f}ms |",
        "",
        "## By Language",
        "",
        "| Language | Queries | Hit@1 | Hit@8 |",
        "|----------|---------|-------|-------|",
    ]
    for lang in ("tr", "en"):
        lang_rows = [r for r in rows if r["lang"] == lang]
        if lang_rows:
            lh1 = sum(r["hit_1"] for r in lang_rows) / len(lang_rows)
            lh8 = sum(r["hit_8"] for r in lang_rows) / len(lang_rows)
            lines.append(f"| {lang.upper()} | {len(lang_rows)} | {lh1:.1%} | {lh8:.1%} |")

    lines += [
        "",
        "## Per-Query Results",
        "",
        "| # | Lang | Episode | Question | Rank | Hit@1 | Hit@3 | Hit@5 | Distance | Latency |",
        "|---|------|---------|----------|------|-------|-------|-------|----------|---------|",
    ]
    for i, r in enumerate(rows, 1):
        rank_str = str(r["rank"]) if r["rank"] else "**MISS**"
        h1 = "✓" if r["hit_1"] else "✗"
        h3 = "✓" if r["hit_3"] else "✗"
        h5 = "✓" if r["hit_5"] else "✗"
        dist = str(r["top_distance"]) if r["top_distance"] is not None else "—"
        q = r["question"][:55] + "…" if len(r["question"]) > 55 else r["question"]
        lines.append(
            f"| {i} | {r['lang'].upper()} | {r['episode']} | {q} "
            f"| {rank_str} | {h1} | {h3} | {h5} | {dist} | {r['latency_ms']}ms |"
        )

    lines += [
        "",
        "## Misses",
        "",
    ]
    misses = [r for r in rows if not r["hit_8"]]
    if misses:
        for r in misses:
            lines += [
                f"- **[{r['lang'].upper()}]** `{r['question']}`",
                f"  - Expected: {r['episode']}",
                f"  - Top result: {r['top_title']}",
                "",
            ]
    else:
        lines.append("No misses — all queries found expected source in top 8.")

    out.write_text("\n".join(lines))
    print(f"\nResults saved → {out}")


def main():
    parser = argparse.ArgumentParser(description="Brainpack retrieval benchmark")
    parser.add_argument("--pack", default="armag-2", help="Pack ID to benchmark")
    parser.add_argument("--label", default="baseline", help="Label for result file")
    parser.add_argument("--n-results", type=int, default=8, help="Final number of results to evaluate")
    parser.add_argument("--n-candidates", type=int, default=20, help="Candidates fetched before reranking")
    parser.add_argument("--reranker", default="", help="Cross-encoder model ID for reranking (e.g. cross-encoder/ms-marco-MiniLM-L-6-v2)")
    parser.add_argument("--embedding-model", default="", dest="embedding_model_override", help="Override bi-encoder for in-memory query test (e.g. paraphrase-multilingual-mpnet-base-v2)")
    parser.add_argument("--description", default="", help="Short description of this run")
    args = parser.parse_args()

    run_benchmark(
        pack=args.pack,
        label=args.label,
        n_results=args.n_results,
        description=args.description,
        reranker=args.reranker,
        n_candidates=args.n_candidates,
        embedding_model_override=args.embedding_model_override,
    )


if __name__ == "__main__":
    main()
