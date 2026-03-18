# Retrieval Benchmark — Summary

**Pack:** armag-2 (8 YouTube episodes, Turkish + English)
**Golden dataset:** 24 queries — 16 Turkish, 8 English
**Evaluated at:** Hit@1, Hit@3, Hit@5, Hit@8, MRR

---

## Comparison Table

| Run | Whisper | Bi-encoder | Reranker | Hit@1 | Hit@3 | Hit@5 | Hit@8 | MRR | Latency (mean) |
|-----|---------|-----------|----------|-------|-------|-------|-------|-----|----------------|
| baseline | small | all-MiniLM-L6-v2 | — | 62% | 75% | 83% | 92% | 0.705 | 16.8ms |
| larger-n | small | all-MiniLM-L6-v2 | — | 62% | 71% | 79% | 92% | 0.701 | 16.8ms |
| rerank-marco | small | all-MiniLM-L6-v2 | ms-marco-MiniLM-L-6-v2 | 71% | 79% | 83% | 83% | 0.760 | 92.8ms |
| rerank-bge | small | all-MiniLM-L6-v2 | BAAI/bge-reranker-base | 62% | 75% | 79% | 92% | 0.717 | 186.4ms |
| multilingual-biencoder† | small | paraphrase-multilingual-mpnet-base-v2 | — | 83% | 96% | 100% | 100% | 0.892 | 99.6ms |
| multilingual-plus-bge† | small | paraphrase-multilingual-mpnet-base-v2 | BAAI/bge-reranker-base | 71% | 92% | 96% | 96% | 0.821 | 118.6ms |
| **medium-whisper-multilingual** | **medium** | **paraphrase-multilingual-mpnet-base-v2** | **—** | **83%** | **92%** | **96%** | **100%** | **0.885** | **19.5ms** |

† In-memory re-index test (not a full rebuild — latency includes re-embedding overhead)

## By Language — Baseline vs Final

| Language | Queries | Baseline Hit@1 | Baseline Hit@8 | Final Hit@1 | Final Hit@8 |
|----------|---------|---------------|----------------|-------------|-------------|
| Turkish | 16 | 62% | 88% | 88% | 100% |
| English | 8 | 62% | 100% | 75% | 100% |
| **Total** | **24** | **62%** | **92%** | **83%** | **100%** |

---

## Key Findings

### 1. The bi-encoder choice dominates everything else

Switching from `all-MiniLM-L6-v2` (English-trained, 384-dim) to
`paraphrase-multilingual-mpnet-base-v2` (50+ languages, 768-dim) produced the
largest gain by far — more than any reranking strategy:

- Hit@8: 92% → **100%** (zero misses)
- Hit@1: 62% → **83%** (+21 pp)
- MRR: 0.705 → **0.892** (+0.187)

This is a single config line change: `embedding_model: paraphrase-multilingual-mpnet-base-v2`.

### 2. English-only cross-encoders actively hurt multilingual packs

The ms-marco cross-encoder is trained on English MS MARCO passages. Applied to
Turkish transcript chunks, it cannot judge relevance correctly and **dropped
Hit@8 from 92% to 83%** — worse than the baseline. Adding a reranker is not
neutral; a language-mismatched one is actively harmful.

### 3. Adding a reranker on top of a strong bi-encoder hurts

The BGE reranker (multilingual) on top of `paraphrase-multilingual-mpnet-base-v2`
regressed from 100% to 96% Hit@8 and MRR from 0.892 to 0.821. When the
bi-encoder already retrieves high-quality candidates, the reranker adds noise
by second-guessing correct rankings. Rerankers help most when the bi-encoder
is weak; they are redundant or harmful when the bi-encoder is already strong.

### 4. The misses were always in the index — just ranked too low

At n=20 retrieval, both baseline misses appear:
- "müzik ekipmanları ve ses düzeni" → rank 18
- "yazılım sektöründe dolandırıcılık ve sahtecilik" → rank 13

This confirms the problem is **ranking quality, not index coverage**. The
correct chunks exist; `all-MiniLM-L6-v2` simply cannot measure Turkish semantic
similarity accurately enough to rank them in the top 8.

### 5. Latency trade-off is acceptable

The multilingual model is ~6× slower per query (17ms → 100ms). For a RAG
pipeline where the LLM call dominates (typically 500ms–5s), this is negligible.

---

## Recommended Configuration

```yaml
embedding_model: paraphrase-multilingual-mpnet-base-v2
```

No reranker needed. This single change eliminates all misses on the test pack
and improves both Turkish and English retrieval quality simultaneously.

---

## Note on Transcription Quality

The final run (`medium-whisper-multilingual`) uses a full rebuild with
`whisper-medium` + `paraphrase-multilingual-mpnet-base-v2`. Retrieval metrics
are nearly identical to the in-memory multilingual test (MRR 0.885 vs 0.892),
suggesting the multilingual embedding model is robust enough to compensate for
whisper-small transcription noise at the **retrieval** level.

However, whisper-medium produces significantly cleaner transcripts — technical
terms, code-switching, and proper nouns are transcribed more accurately. This
matters for **answer quality**: the LLM reads the raw transcript text to form
its response, so cleaner transcripts lead to better, more precise answers even
when retrieval ranks are identical. This improvement is real but not captured
by Hit@k or MRR metrics.
