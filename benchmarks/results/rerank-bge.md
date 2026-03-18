# Retrieval Benchmark — rerank-bge

**Date:** 2026-03-18 07:30  
**Pack:** armag-2  
**Embedding model:** all-MiniLM-L6-v2  
**n_results:** 8  
**Reranker:** BAAI/bge-reranker-base  
**n_candidates:** 20  
**Queries:** 24 (16 Turkish, 8 English)  
**Description:** Cross-encoder reranking: BAAI/bge-reranker-base (multilingual), 20 candidates → top 8  

## Summary

| Metric | Value |
|--------|-------|
| Hit Rate@1 | 62.5% |
| Hit Rate@3 | 75.0% |
| Hit Rate@5 | 79.2% |
| Hit Rate@8 | 91.7% |
| MRR@8 | 0.717 |
| Latency (mean) | 186.4ms |
| Latency (p95) | 767.8ms |

## By Language

| Language | Queries | Hit@1 | Hit@8 |
|----------|---------|-------|-------|
| TR | 16 | 62.5% | 93.8% |
| EN | 8 | 62.5% | 87.5% |

## Per-Query Results

| # | Lang | Episode | Question | Rank | Hit@1 | Hit@3 | Hit@5 | Distance | Latency |
|---|------|---------|----------|------|-------|-------|-------|----------|---------|
| 1 | TR | ChatGPT, AI, Prompt Engineering | ChatGPT ve prompt engineering hakkında neler konuşuldu? | 1 | ✓ | ✓ | ✓ | 0.7535 | 1160.7ms |
| 2 | TR | ChatGPT, AI, Prompt Engineering | Yapay zeka ile kod yazmak ve öğrencilere kullandırmak | 1 | ✓ | ✓ | ✓ | 0.638 | 115.5ms |
| 3 | EN | ChatGPT, AI, Prompt Engineering | AI code generation and teaching students | 1 | ✓ | ✓ | ✓ | 1.4007 | 767.8ms |
| 4 | TR | Elektronik ve Müzik Hobileri | elektrik gitar pedal ve elektronik hobiler | 1 | ✓ | ✓ | ✓ | 0.801 | 100.7ms |
| 5 | TR | Elektronik ve Müzik Hobileri | müzik ekipmanları ve ses düzeni | 6 | ✗ | ✗ | ✗ | 0.7052 | 113.2ms |
| 6 | EN | Elektronik ve Müzik Hobileri | guitar pedals and electronics hobby | 1 | ✓ | ✓ | ✓ | 1.36 | 101.6ms |
| 7 | TR | JSDoc, Architecture Patterns | yazılım mimarisi hexagonal onion clean architecture | 1 | ✓ | ✓ | ✓ | 1.1256 | 142.1ms |
| 8 | TR | JSDoc, Architecture Patterns | JSDoc kullanımı ve faydaları | 2 | ✗ | ✓ | ✓ | 0.6457 | 155.7ms |
| 9 | EN | JSDoc, Architecture Patterns | software architecture layered hexagonal design patterns | 6 | ✗ | ✗ | ✗ | 1.5933 | 164.7ms |
| 10 | TR | ADHD, Kişisel Gelişim | ADHD ile çalışmak ve planlı yaşam | 1 | ✓ | ✓ | ✓ | 0.4409 | 119.1ms |
| 11 | TR | ADHD, Kişisel Gelişim | uyku düzeni ve kişisel verimlilik | 1 | ✓ | ✓ | ✓ | 0.9881 | 103.5ms |
| 12 | EN | ADHD, Kişisel Gelişim | ADHD productivity and personal development in software | 2 | ✗ | ✓ | ✓ | 1.4336 | 116.7ms |
| 13 | TR | Kütüphane Yazımı, Composition API | Vue Composition API ve Options API karşılaştırması | 1 | ✓ | ✓ | ✓ | 0.8701 | 127.8ms |
| 14 | TR | Kütüphane Yazımı, Composition API | JavaScript kütüphanesi nasıl yazılır | 1 | ✓ | ✓ | ✓ | 0.7547 | 114.1ms |
| 15 | EN | Kütüphane Yazımı, Composition API | how to build a JavaScript library composition vs option… | 1 | ✓ | ✓ | ✓ | 1.3087 | 112.8ms |
| 16 | TR | Sabancı, Global Ekonomi | global ekonomi ve para birimleri arasındaki fark | 1 | ✓ | ✓ | ✓ | 0.3662 | 101.9ms |
| 17 | TR | Sabancı, Global Ekonomi | Sabancı üniversitesi yazılım mühendisliği deneyimi | 2 | ✗ | ✓ | ✓ | 0.6399 | 99.3ms |
| 18 | EN | Sabancı, Global Ekonomi | women in software engineering and global economy | **MISS** | ✗ | ✗ | ✗ | 1.4002 | 124.8ms |
| 19 | TR | Dolandırıcılık, Software Testing | yazılım sektöründe dolandırıcılık ve sahtecilik | **MISS** | ✗ | ✗ | ✗ | 0.5832 | 108.9ms |
| 20 | TR | Dolandırıcılık, Software Testing | software testing önemi ve test yazma | 5 | ✗ | ✗ | ✓ | 1.251 | 102.8ms |
| 21 | EN | Dolandırıcılık, Software Testing | software scams fraud and testing practices | 1 | ✓ | ✓ | ✓ | 1.6318 | 92.4ms |
| 22 | TR | İşten Çıkarmalar, Yöneticilik | işten çıkarmalar neden oluyor ve nasıl önlenir | 6 | ✗ | ✗ | ✗ | 0.5903 | 114.9ms |
| 23 | TR | İşten Çıkarmalar, Yöneticilik | iyi yönetici nasıl olunur liderlik | 1 | ✓ | ✓ | ✓ | 0.6217 | 108.7ms |
| 24 | EN | İşten Çıkarmalar, Yöneticilik | tech layoffs and management unit of work pattern | 1 | ✓ | ✓ | ✓ | 1.1447 | 103.9ms |

## Misses

- **[EN]** `women in software engineering and global economy`
  - Expected: Sabancı, Global Ekonomi
  - Top result: Yazılım sektöründeki dolandırıcılık, software testing #vebirsuruseydaha

- **[TR]** `yazılım sektöründe dolandırıcılık ve sahtecilik`
  - Expected: Dolandırıcılık, Software Testing
  - Top result: İşten çıkarmalar, Yöneticilik, Unit of Work
