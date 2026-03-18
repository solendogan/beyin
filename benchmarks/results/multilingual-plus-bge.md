# Retrieval Benchmark — multilingual-plus-bge

**Date:** 2026-03-18 07:32  
**Pack:** armag-2  
**Embedding model:** paraphrase-multilingual-mpnet-base-v2  
**n_results:** 8  
**Index embedding model:** all-MiniLM-L6-v2 (index built with this)  
**Reranker:** BAAI/bge-reranker-base  
**n_candidates:** 20  
**Queries:** 24 (16 Turkish, 8 English)  
**Description:** Combined: multilingual mpnet bi-encoder + BGE reranker, 20 candidates → top 8  

## Summary

| Metric | Value |
|--------|-------|
| Hit Rate@1 | 70.8% |
| Hit Rate@3 | 91.7% |
| Hit Rate@5 | 95.8% |
| Hit Rate@8 | 95.8% |
| MRR@8 | 0.821 |
| Latency (mean) | 118.6ms |
| Latency (p95) | 184.4ms |

## By Language

| Language | Queries | Hit@1 | Hit@8 |
|----------|---------|-------|-------|
| TR | 16 | 68.8% | 100.0% |
| EN | 8 | 75.0% | 87.5% |

## Per-Query Results

| # | Lang | Episode | Question | Rank | Hit@1 | Hit@3 | Hit@5 | Distance | Latency |
|---|------|---------|----------|------|-------|-------|-------|----------|---------|
| 1 | TR | ChatGPT, AI, Prompt Engineering | ChatGPT ve prompt engineering hakkında neler konuşuldu? | 1 | ✓ | ✓ | ✓ | 0.427 | 184.4ms |
| 2 | TR | ChatGPT, AI, Prompt Engineering | Yapay zeka ile kod yazmak ve öğrencilere kullandırmak | 2 | ✗ | ✓ | ✓ | 0.4652 | 228.5ms |
| 3 | EN | ChatGPT, AI, Prompt Engineering | AI code generation and teaching students | 1 | ✓ | ✓ | ✓ | 0.2443 | 109.5ms |
| 4 | TR | Elektronik ve Müzik Hobileri | elektrik gitar pedal ve elektronik hobiler | 1 | ✓ | ✓ | ✓ | 0.3023 | 113.5ms |
| 5 | TR | Elektronik ve Müzik Hobileri | müzik ekipmanları ve ses düzeni | 1 | ✓ | ✓ | ✓ | 0.3962 | 138.4ms |
| 6 | EN | Elektronik ve Müzik Hobileri | guitar pedals and electronics hobby | 1 | ✓ | ✓ | ✓ | 0.2866 | 108.7ms |
| 7 | TR | JSDoc, Architecture Patterns | yazılım mimarisi hexagonal onion clean architecture | 1 | ✓ | ✓ | ✓ | 0.6953 | 116.4ms |
| 8 | TR | JSDoc, Architecture Patterns | JSDoc kullanımı ve faydaları | 2 | ✗ | ✓ | ✓ | 0.6219 | 116.8ms |
| 9 | EN | JSDoc, Architecture Patterns | software architecture layered hexagonal design patterns | 1 | ✓ | ✓ | ✓ | 0.5847 | 103.5ms |
| 10 | TR | ADHD, Kişisel Gelişim | ADHD ile çalışmak ve planlı yaşam | 1 | ✓ | ✓ | ✓ | 0.2976 | 116.5ms |
| 11 | TR | ADHD, Kişisel Gelişim | uyku düzeni ve kişisel verimlilik | 1 | ✓ | ✓ | ✓ | 0.2747 | 134.7ms |
| 12 | EN | ADHD, Kişisel Gelişim | ADHD productivity and personal development in software | 2 | ✗ | ✓ | ✓ | 0.6045 | 123.1ms |
| 13 | TR | Kütüphane Yazımı, Composition API | Vue Composition API ve Options API karşılaştırması | 1 | ✓ | ✓ | ✓ | 0.4097 | 105.2ms |
| 14 | TR | Kütüphane Yazımı, Composition API | JavaScript kütüphanesi nasıl yazılır | 1 | ✓ | ✓ | ✓ | 0.6282 | 87.8ms |
| 15 | EN | Kütüphane Yazımı, Composition API | how to build a JavaScript library composition vs option… | 1 | ✓ | ✓ | ✓ | 0.5597 | 90.2ms |
| 16 | TR | Sabancı, Global Ekonomi | global ekonomi ve para birimleri arasındaki fark | 1 | ✓ | ✓ | ✓ | 0.1651 | 85.5ms |
| 17 | TR | Sabancı, Global Ekonomi | Sabancı üniversitesi yazılım mühendisliği deneyimi | 2 | ✗ | ✓ | ✓ | 0.4599 | 96.4ms |
| 18 | EN | Sabancı, Global Ekonomi | women in software engineering and global economy | 1 | ✓ | ✓ | ✓ | 0.331 | 102.8ms |
| 19 | TR | Dolandırıcılık, Software Testing | yazılım sektöründe dolandırıcılık ve sahtecilik | 2 | ✗ | ✓ | ✓ | 0.6107 | 114.2ms |
| 20 | TR | Dolandırıcılık, Software Testing | software testing önemi ve test yazma | 5 | ✗ | ✗ | ✓ | 0.5485 | 113.7ms |
| 21 | EN | Dolandırıcılık, Software Testing | software scams fraud and testing practices | **MISS** | ✗ | ✗ | ✗ | 0.5818 | 115.7ms |
| 22 | TR | İşten Çıkarmalar, Yöneticilik | işten çıkarmalar neden oluyor ve nasıl önlenir | 1 | ✓ | ✓ | ✓ | 0.2475 | 105.5ms |
| 23 | TR | İşten Çıkarmalar, Yöneticilik | iyi yönetici nasıl olunur liderlik | 1 | ✓ | ✓ | ✓ | 0.2895 | 102.7ms |
| 24 | EN | İşten Çıkarmalar, Yöneticilik | tech layoffs and management unit of work pattern | 1 | ✓ | ✓ | ✓ | 0.5499 | 132.9ms |

## Misses

- **[EN]** `software scams fraud and testing practices`
  - Expected: Dolandırıcılık, Software Testing
  - Top result: İşten çıkarmalar, Yöneticilik, Unit of Work
