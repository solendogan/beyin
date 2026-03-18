# Retrieval Benchmark — Full Summary

**Pack:** armag-2 (8 YouTube episodes, Turkish + English podcast content)
**Total runs:** 9 (7 on standard dataset, 2 on hard dataset)
**Datasets:** Standard (24 queries), Hard (24 queries)
**Metrics:** Hit@1, Hit@3, Hit@5, Hit@8, MRR, latency mean/p95

---

## All Runs at a Glance

| # | Label | Whisper | Bi-encoder | Reranker | Dataset | Hit@1 | Hit@3 | Hit@5 | Hit@8 | MRR | Latency |
|---|-------|---------|-----------|----------|---------|-------|-------|-------|-------|-----|---------|
| 1 | baseline | small | all-MiniLM-L6-v2 | — | standard | 62% | 75% | 83% | 92% | 0.705 | 16.8ms |
| 2 | larger-n | small | all-MiniLM-L6-v2 | — | standard | 62% | 71% | 79% | 92% | 0.701 | 16.8ms |
| 3 | rerank-marco | small | all-MiniLM-L6-v2 | ms-marco-MiniLM-L-6-v2 | standard | 71% | 79% | 83% | 83% | 0.760 | 92.8ms |
| 4 | rerank-bge | small | all-MiniLM-L6-v2 | BAAI/bge-reranker-base | standard | 62% | 75% | 79% | 92% | 0.717 | 186.4ms |
| 5 | multilingual-biencoder† | small | paraphrase-multilingual-mpnet-base-v2 | — | standard | 83% | 96% | 100% | 100% | 0.892 | 99.6ms |
| 6 | multilingual-plus-bge† | small | paraphrase-multilingual-mpnet-base-v2 | BAAI/bge-reranker-base | standard | 71% | 92% | 96% | 96% | 0.821 | 118.6ms |
| 7 | medium-whisper-multilingual | medium | paraphrase-multilingual-mpnet-base-v2 | — | standard | 83% | 92% | 96% | 100% | 0.885 | 19.5ms |
| 8 | hard-small-whisper | small | paraphrase-multilingual-mpnet-base-v2 | — | hard | 79% | 92% | 92% | 96% | 0.854 | 19.2ms |
| 9 | hard-medium-whisper | medium | paraphrase-multilingual-mpnet-base-v2 | — | hard | 79% | 88% | 92% | 96% | 0.851 | 20.5ms |

† In-memory re-index: all chunks re-embedded on-the-fly. Latency includes re-embedding overhead and is not representative of production query speed.

---

## By Language — Baseline vs Final (standard dataset)

| Language | Queries | Baseline Hit@1 | Baseline Hit@8 | Final Hit@1 | Final Hit@8 |
|----------|---------|---------------|----------------|-------------|-------------|
| Turkish | 16 | 62% | 88% | 88% | 100% |
| English | 8 | 62% | 100% | 75% | 100% |
| **Total** | **24** | **62%** | **92%** | **83%** | **100%** |

---

## Step-by-Step Story

### Step 1 — Baseline: What we started with (Run 1)

The initial brainpack implementation used `all-MiniLM-L6-v2` as the embedding
model — the most common default in the sentence-transformers ecosystem. Fast,
well-documented, widely used. Transcription used `whisper-small`, the fastest
Whisper variant. Pack was built from 8 Turkish/English YouTube episodes.

**Results: Hit@8=92%, MRR=0.705, latency=16.8ms**

At first glance 92% looks acceptable. But 2 queries completely missed:
- "müzik ekipmanları ve ses düzeni" → MISS (correct episode absent from top 8)
- "yazılım sektöründe dolandırıcılık ve sahtecilik" → MISS

Both are Turkish queries. English queries hit 100% at Hit@8. This hints at a
language gap in the embedding model.

---

### Step 2 — Diagnosing the misses: Are the chunks even in the index? (Run 2)

Before trying fixes, we retrieved n=20 results instead of n=8 to see where the
missed chunks actually rank.

**Results: Hit@8=92% (same), but now we can see:**
- "müzik ekipmanları ve ses düzeni" → rank 18
- "yazılım sektöründe dolandırıcılık" → rank 13

**Key finding:** The correct chunks ARE in the index — they just rank poorly.
This is a ranking quality problem, not a coverage problem. The right content
exists; `all-MiniLM-L6-v2` cannot measure Turkish semantic similarity
accurately enough to surface it in the top 8.

This matters for the fix strategy: we don't need more data or different
chunking — we need a better ranking model.

---

### Step 3 — The obvious fix that backfires: English cross-encoder (Run 3)

The standard retrieval improvement playbook says: add a cross-encoder reranker.
Retrieve more candidates with the bi-encoder, then rerank with a more powerful
cross-encoder. We tried `cross-encoder/ms-marco-MiniLM-L-6-v2`, a popular
English cross-encoder trained on MS MARCO.

Setup: retrieve 20 candidates with all-MiniLM-L6-v2, rerank to top 8.

**Results: Hit@1=71% (+9pp), MRR=0.760 (+0.055) — but Hit@8 dropped to 83% (-9pp)**

The cross-encoder improved English query ranking (Hit@1 up) but actively hurt
Turkish content. It pushed correct Turkish chunks out of the top 8 entirely.
"software testing önemi ve test yazma" went from rank 1 (baseline) to MISS.

The ms-marco cross-encoder is trained exclusively on English. Applied to
Turkish transcript chunks, it cannot assess relevance and introduces systematic
errors. **A language-mismatched reranker is actively harmful, not neutral.**
Latency also jumped 5.5× (16.8ms → 92.8ms).

---

### Step 4 — Trying a multilingual reranker (Run 4)

We replaced ms-marco with `BAAI/bge-reranker-base`, a multilingual cross-encoder
that supports Turkish. Same setup: 20 candidates → rerank to top 8.

**Results: Hit@8=92% (baseline level), MRR=0.717 (+0.012), latency=186.4ms**

BGE reranker fixed one miss ("müzik ekipmanları" moved to rank 6) but
"dolandırıcılık" still missed. MRR improved only marginally (+0.012 vs baseline).
Latency exploded to 186.4ms mean, 767ms p95 — 11× slower than baseline.

The multilingual reranker is safer than ms-marco but delivers only marginal gains
at a severe latency cost. **Rerankers work best when the bi-encoder retrieves
reasonable candidates. When the bi-encoder itself is the problem, reranking
cannot fully compensate.**

---

### Step 5 — The real fix: swap the bi-encoder (Run 5)

Instead of patching retrieval with a reranker, we changed the fundamental
question: what if we used a model that actually understands Turkish?

`paraphrase-multilingual-mpnet-base-v2` (768-dim) was trained on parallel
corpora across 50+ languages including Turkish. We tested it via an in-memory
re-index: all 696 chunks fetched from ChromaDB and re-embedded with the new
model, then queried with cosine similarity. No pack rebuild required for this
test.

**Results: Hit@1=83% (+21pp), Hit@3=96%, Hit@5=100%, Hit@8=100%, MRR=0.892 (+0.187)**

Zero misses. Both previously missing Turkish queries now rank 1. This is the
largest gain across all experiments — produced by a single model swap. Turkish
Hit@8 went from 88% to 100%; English from 100% to 100% (maintained).

The latency of 99.6ms in this run is misleading — it includes re-embedding
overhead (model loading + 696 chunks re-encoded per test run). Real production
latency with a proper indexed pack is shown in Run 7.

---

### Step 6 — Does adding a reranker on top help further? (Run 6)

With the strong multilingual bi-encoder in place, we tested adding the BGE
reranker on top: multilingual bi-encoder retrieves 20 candidates, BGE reranks
to top 8.

**Results: Hit@1=71% (-12pp vs Run 5), Hit@8=96% (-4pp), MRR=0.821 (-0.071)**

Worse across the board. The reranker regressed from the bi-encoder-alone result.
"software scams fraud and testing practices" went from rank 1 to MISS.

**Key insight:** Rerankers add value when the bi-encoder is weak and retrieves
noisy candidates. When the bi-encoder already retrieves high-quality candidates,
the reranker introduces noise by second-guessing correct rankings. Adding
complexity hurt here. The best pipeline is the simplest one.

---

### Step 7 — Production rebuild: real latency numbers (Run 7)

Runs 5 and 6 used in-memory re-indexing. Run 7 is a proper full rebuild:
pack rebuilt from scratch with `whisper-medium` transcription and
`paraphrase-multilingual-mpnet-base-v2` embeddings stored in ChromaDB.

**Results: Hit@1=83%, Hit@8=100%, MRR=0.885, latency=19.5ms**

The real production latency with the multilingual model is **19.5ms** —
barely different from the baseline 16.8ms. The in-memory test (99.6ms) was
slow due to re-embedding overhead, not the query itself. ChromaDB vector
search is fast regardless of embedding dimensionality.

MRR is 0.885 vs 0.892 in the in-memory test — a tiny gap likely explained by
slightly different chunking from the medium whisper transcripts (640 chunks vs
696 in the in-memory test which used the small whisper index).

---

### Step 8 & 9 — Hard queries: does whisper-medium actually help retrieval?

We designed a 24-query "hard" dataset specifically targeting content that
whisper-small commonly mishears: product model numbers (Roland GK3, Boss GM800),
acronyms (MIDI, CBT, TDD), mixed Turkish/English technical terms (Composition API,
Unit of Work, AstroJS, JSDoc), and brand names (Udemy, GitHub Copilot, OpenAI).

We rebuilt the pack with small whisper, ran the hard benchmark, then rebuilt
with medium whisper, and ran it again.

| | Whisper | Hit@1 | Hit@3 | Hit@5 | Hit@8 | MRR | Latency |
|---|---------|-------|-------|-------|-------|-----|---------|
| Run 8 | small | 79% | 92% | 92% | 96% | 0.854 | 19.2ms |
| Run 9 | medium | 79% | 88% | 92% | 96% | 0.851 | 20.5ms |

**Results: statistically identical.** The single miss on both runs is
"unit testing TDD test driven development practices" — which is a semantics
problem (the episode covers software fraud and testing culture, not TDD
methodology), not a transcription problem.

**Key finding:** `paraphrase-multilingual-mpnet-base-v2` is robust enough to
transcription noise that even whisper-small transcripts produce the same
retrieval quality as whisper-medium. The multilingual embedding space captures
semantic intent even when specific technical terms are slightly garbled.

---

## Summary of Findings

### Finding 1: The bi-encoder model is the dominant lever
The single most impactful change in the entire experiment series was swapping
`all-MiniLM-L6-v2` for `paraphrase-multilingual-mpnet-base-v2`. This one config
line change:
- Eliminated all retrieval misses (92% → 100% Hit@8)
- Improved MRR by 26% (0.705 → 0.892)
- Improved Hit@1 by 21 percentage points
- Added only ~3ms to production query latency (16.8ms → 19.5ms)

### Finding 2: English-only rerankers are harmful for multilingual content
`cross-encoder/ms-marco-MiniLM-L-6-v2` dropped Hit@8 from 92% to 83% by
misranking Turkish chunks. An English-only model scoring Turkish text introduces
systematic errors. Worse than no reranker at all.

### Finding 3: Even a multilingual reranker hurts a good bi-encoder
`BAAI/bge-reranker-base` on top of `paraphrase-multilingual-mpnet-base-v2`
regressed from 100% to 96% Hit@8. Rerankers add value when compensating for a
weak bi-encoder; they add noise when the bi-encoder is already strong.

### Finding 4: Misses are a ranking problem, not a coverage problem
At n=20, both baseline misses appeared (ranks 13 and 18). The content was
indexed correctly; the embedding model simply couldn't rank Turkish semantic
similarity well enough. This diagnosis directly pointed to the bi-encoder swap.

### Finding 5: Whisper-medium doesn't improve retrieval — but still matters
Hard queries targeting terms whisper-small commonly mishears showed identical
retrieval quality between small and medium transcripts. The multilingual
embedding model compensates for transcription noise at the semantic level.

However, whisper-medium still meaningfully improves **answer quality**: the LLM
reads the raw transcript text to generate responses, and cleaner transcription
of technical terms (framework names, product numbers, API names) produces more
accurate and precise answers. This improvement is real but not captured by
retrieval metrics (Hit@k, MRR).

### Finding 6: Production latency is not a concern
- Baseline: 16.8ms
- Final (multilingual mpnet, ChromaDB): 19.5ms
- The in-memory test showing 99.6ms was re-embedding overhead, not query overhead
- BGE reranker adds ~170ms mean, 700ms+ p95 — a real cost with minimal gain

---

## Recommended Configuration

```yaml
embedding_model: paraphrase-multilingual-mpnet-base-v2
```

No reranker. This single change eliminates all misses on Turkish/multilingual
content and maintains full English retrieval quality at near-baseline latency.

For transcription: `whisper-medium` is recommended for cleaner LLM answers,
especially on content that mixes Turkish with English technical terms. It does
not improve retrieval metrics but improves the quality of text the LLM reads.
