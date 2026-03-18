# Retrieval Benchmark — rerank-marco

**Date:** 2026-03-18 07:29  
**Pack:** armag-2  
**Embedding model:** all-MiniLM-L6-v2  
**n_results:** 8  
**Reranker:** cross-encoder/ms-marco-MiniLM-L-6-v2  
**n_candidates:** 20  
**Queries:** 24 (16 Turkish, 8 English)  
**Description:** Cross-encoder reranking: ms-marco-MiniLM-L-6-v2, 20 candidates → top 8  

## Summary

| Metric | Value |
|--------|-------|
| Hit Rate@1 | 70.8% |
| Hit Rate@3 | 79.2% |
| Hit Rate@5 | 83.3% |
| Hit Rate@8 | 83.3% |
| MRR@8 | 0.760 |
| Latency (mean) | 92.8ms |
| Latency (p95) | 153.6ms |

## By Language

| Language | Queries | Hit@1 | Hit@8 |
|----------|---------|-------|-------|
| TR | 16 | 62.5% | 81.2% |
| EN | 8 | 87.5% | 87.5% |

## Per-Query Results

| # | Lang | Episode | Question | Rank | Hit@1 | Hit@3 | Hit@5 | Distance | Latency |
|---|------|---------|----------|------|-------|-------|-------|----------|---------|
| 1 | TR | ChatGPT, AI, Prompt Engineering | ChatGPT ve prompt engineering hakkında neler konuşuldu? | 1 | ✓ | ✓ | ✓ | 0.7539 | 429.7ms |
| 2 | TR | ChatGPT, AI, Prompt Engineering | Yapay zeka ile kod yazmak ve öğrencilere kullandırmak | 1 | ✓ | ✓ | ✓ | 0.5644 | 72.7ms |
| 3 | EN | ChatGPT, AI, Prompt Engineering | AI code generation and teaching students | 1 | ✓ | ✓ | ✓ | 1.4007 | 153.6ms |
| 4 | TR | Elektronik ve Müzik Hobileri | elektrik gitar pedal ve elektronik hobiler | 1 | ✓ | ✓ | ✓ | 0.801 | 107.4ms |
| 5 | TR | Elektronik ve Müzik Hobileri | müzik ekipmanları ve ses düzeni | **MISS** | ✗ | ✗ | ✗ | 0.6577 | 58.8ms |
| 6 | EN | Elektronik ve Müzik Hobileri | guitar pedals and electronics hobby | 1 | ✓ | ✓ | ✓ | 1.1769 | 101.8ms |
| 7 | TR | JSDoc, Architecture Patterns | yazılım mimarisi hexagonal onion clean architecture | 1 | ✓ | ✓ | ✓ | 0.9695 | 50.9ms |
| 8 | TR | JSDoc, Architecture Patterns | JSDoc kullanımı ve faydaları | 4 | ✗ | ✗ | ✓ | 0.6457 | 153.2ms |
| 9 | EN | JSDoc, Architecture Patterns | software architecture layered hexagonal design patterns | 1 | ✓ | ✓ | ✓ | 1.3572 | 59.8ms |
| 10 | TR | ADHD, Kişisel Gelişim | ADHD ile çalışmak ve planlı yaşam | 1 | ✓ | ✓ | ✓ | 0.4409 | 123.6ms |
| 11 | TR | ADHD, Kişisel Gelişim | uyku düzeni ve kişisel verimlilik | 2 | ✗ | ✓ | ✓ | 0.9937 | 51.3ms |
| 12 | EN | ADHD, Kişisel Gelişim | ADHD productivity and personal development in software | 1 | ✓ | ✓ | ✓ | 1.1547 | 43.7ms |
| 13 | TR | Kütüphane Yazımı, Composition API | Vue Composition API ve Options API karşılaştırması | 1 | ✓ | ✓ | ✓ | 0.8701 | 62.3ms |
| 14 | TR | Kütüphane Yazımı, Composition API | JavaScript kütüphanesi nasıl yazılır | 2 | ✗ | ✓ | ✓ | 0.387 | 48.8ms |
| 15 | EN | Kütüphane Yazımı, Composition API | how to build a JavaScript library composition vs option… | 1 | ✓ | ✓ | ✓ | 1.3087 | 46.6ms |
| 16 | TR | Sabancı, Global Ekonomi | global ekonomi ve para birimleri arasındaki fark | 1 | ✓ | ✓ | ✓ | 0.3662 | 39.6ms |
| 17 | TR | Sabancı, Global Ekonomi | Sabancı üniversitesi yazılım mühendisliği deneyimi | 1 | ✓ | ✓ | ✓ | 0.4772 | 56.7ms |
| 18 | EN | Sabancı, Global Ekonomi | women in software engineering and global economy | **MISS** | ✗ | ✗ | ✗ | 1.4382 | 68.5ms |
| 19 | TR | Dolandırıcılık, Software Testing | yazılım sektöründe dolandırıcılık ve sahtecilik | **MISS** | ✗ | ✗ | ✗ | 0.584 | 136.7ms |
| 20 | TR | Dolandırıcılık, Software Testing | software testing önemi ve test yazma | **MISS** | ✗ | ✗ | ✗ | 1.22 | 107.1ms |
| 21 | EN | Dolandırıcılık, Software Testing | software scams fraud and testing practices | 1 | ✓ | ✓ | ✓ | 1.6392 | 43.4ms |
| 22 | TR | İşten Çıkarmalar, Yöneticilik | işten çıkarmalar neden oluyor ve nasıl önlenir | 1 | ✓ | ✓ | ✓ | 0.5747 | 64.8ms |
| 23 | TR | İşten Çıkarmalar, Yöneticilik | iyi yönetici nasıl olunur liderlik | 1 | ✓ | ✓ | ✓ | 0.6217 | 52.2ms |
| 24 | EN | İşten Çıkarmalar, Yöneticilik | tech layoffs and management unit of work pattern | 1 | ✓ | ✓ | ✓ | 1.1447 | 94.9ms |

## Misses

- **[TR]** `müzik ekipmanları ve ses düzeni`
  - Expected: Elektronik ve Müzik Hobileri
  - Top result: Sabancı Üniversitesi, Global Ekonomi, Kadın Yazılımcılar

- **[EN]** `women in software engineering and global economy`
  - Expected: Sabancı, Global Ekonomi
  - Top result: İşten çıkarmalar, Yöneticilik, Unit of Work

- **[TR]** `yazılım sektöründe dolandırıcılık ve sahtecilik`
  - Expected: Dolandırıcılık, Software Testing
  - Top result: Sabancı Üniversitesi, Global Ekonomi, Kadın Yazılımcılar

- **[TR]** `software testing önemi ve test yazma`
  - Expected: Dolandırıcılık, Software Testing
  - Top result: Nasıl kütüphane yazılır? Composition API, Options API, React, Angular
