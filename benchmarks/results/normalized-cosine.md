# Retrieval Benchmark — normalized-cosine

**Date:** 2026-03-18 08:29  
**Pack:** armag-2  
**Embedding model:** paraphrase-multilingual-mpnet-base-v2  
**n_results:** 8  
**Queries:** 24 (16 Turkish, 8 English)  
**Description:** multilingual-mpnet + normalized embeddings + cosine distance (bugfix)  

## Summary

| Metric | Value |
|--------|-------|
| Hit Rate@1 | 83.3% |
| Hit Rate@3 | 83.3% |
| Hit Rate@5 | 100.0% |
| Hit Rate@8 | 100.0% |
| MRR@8 | 0.873 |
| Latency (mean) | 20.8ms |
| Latency (p95) | 37.4ms |

## By Language

| Language | Queries | Hit@1 | Hit@8 |
|----------|---------|-------|-------|
| TR | 16 | 87.5% | 100.0% |
| EN | 8 | 75.0% | 100.0% |

## Per-Query Results

| # | Lang | Episode | Question | Rank | Hit@1 | Hit@3 | Hit@5 | Distance | Latency |
|---|------|---------|----------|------|-------|-------|-------|----------|---------|
| 1 | TR | ChatGPT, AI, Prompt Engineering | ChatGPT ve prompt engineering hakkında neler konuşuldu? | 1 | ✓ | ✓ | ✓ | 0.3045 | 106.4ms |
| 2 | TR | ChatGPT, AI, Prompt Engineering | Yapay zeka ile kod yazmak ve öğrencilere kullandırmak | 1 | ✓ | ✓ | ✓ | 0.308 | 31.1ms |
| 3 | EN | ChatGPT, AI, Prompt Engineering | AI code generation and teaching students | 1 | ✓ | ✓ | ✓ | 0.3637 | 27.4ms |
| 4 | TR | Elektronik ve Müzik Hobileri | elektrik gitar pedal ve elektronik hobiler | 1 | ✓ | ✓ | ✓ | 0.317 | 34.9ms |
| 5 | TR | Elektronik ve Müzik Hobileri | müzik ekipmanları ve ses düzeni | 1 | ✓ | ✓ | ✓ | 0.3337 | 37.4ms |
| 6 | EN | Elektronik ve Müzik Hobileri | guitar pedals and electronics hobby | 1 | ✓ | ✓ | ✓ | 0.3116 | 8.3ms |
| 7 | TR | JSDoc, Architecture Patterns | yazılım mimarisi hexagonal onion clean architecture | 1 | ✓ | ✓ | ✓ | 0.4793 | 30.2ms |
| 8 | TR | JSDoc, Architecture Patterns | JSDoc kullanımı ve faydaları | 1 | ✓ | ✓ | ✓ | 0.4268 | 9.2ms |
| 9 | EN | JSDoc, Architecture Patterns | software architecture layered hexagonal design patterns | 1 | ✓ | ✓ | ✓ | 0.429 | 11.2ms |
| 10 | TR | ADHD, Kişisel Gelişim | ADHD ile çalışmak ve planlı yaşam | 1 | ✓ | ✓ | ✓ | 0.2368 | 8.1ms |
| 11 | TR | ADHD, Kişisel Gelişim | uyku düzeni ve kişisel verimlilik | 1 | ✓ | ✓ | ✓ | 0.2746 | 7.2ms |
| 12 | EN | ADHD, Kişisel Gelişim | ADHD productivity and personal development in software | 1 | ✓ | ✓ | ✓ | 0.3433 | 28.7ms |
| 13 | TR | Kütüphane Yazımı, Composition API | Vue Composition API ve Options API karşılaştırması | 1 | ✓ | ✓ | ✓ | 0.314 | 29.4ms |
| 14 | TR | Kütüphane Yazımı, Composition API | JavaScript kütüphanesi nasıl yazılır | 4 | ✗ | ✗ | ✓ | 0.4883 | 9.3ms |
| 15 | EN | Kütüphane Yazımı, Composition API | how to build a JavaScript library composition vs option… | 1 | ✓ | ✓ | ✓ | 0.4712 | 10.9ms |
| 16 | TR | Sabancı, Global Ekonomi | global ekonomi ve para birimleri arasındaki fark | 1 | ✓ | ✓ | ✓ | 0.1651 | 10.6ms |
| 17 | TR | Sabancı, Global Ekonomi | Sabancı üniversitesi yazılım mühendisliği deneyimi | 1 | ✓ | ✓ | ✓ | 0.3635 | 30.5ms |
| 18 | EN | Sabancı, Global Ekonomi | women in software engineering and global economy | 4 | ✗ | ✗ | ✓ | 0.4839 | 11.4ms |
| 19 | TR | Dolandırıcılık, Software Testing | yazılım sektöründe dolandırıcılık ve sahtecilik | 4 | ✗ | ✗ | ✓ | 0.4933 | 8.1ms |
| 20 | TR | Dolandırıcılık, Software Testing | software testing önemi ve test yazma | 1 | ✓ | ✓ | ✓ | 0.4333 | 7.3ms |
| 21 | EN | Dolandırıcılık, Software Testing | software scams fraud and testing practices | 5 | ✗ | ✗ | ✓ | 0.5393 | 7.6ms |
| 22 | TR | İşten Çıkarmalar, Yöneticilik | işten çıkarmalar neden oluyor ve nasıl önlenir | 1 | ✓ | ✓ | ✓ | 0.2594 | 7.8ms |
| 23 | TR | İşten Çıkarmalar, Yöneticilik | iyi yönetici nasıl olunur liderlik | 1 | ✓ | ✓ | ✓ | 0.1889 | 11.3ms |
| 24 | EN | İşten Çıkarmalar, Yöneticilik | tech layoffs and management unit of work pattern | 1 | ✓ | ✓ | ✓ | 0.4042 | 13.8ms |

## Misses

No misses — all queries found expected source in top 8.