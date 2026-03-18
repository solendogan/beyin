# Retrieval Benchmark — multilingual-biencoder

**Date:** 2026-03-18 07:32  
**Pack:** armag-2  
**Embedding model:** paraphrase-multilingual-mpnet-base-v2  
**n_results:** 8  
**Index embedding model:** all-MiniLM-L6-v2 (index built with this)  
**Queries:** 24 (16 Turkish, 8 English)  
**Description:** Multilingual bi-encoder: paraphrase-multilingual-mpnet-base-v2 (in-memory re-index)  

## Summary

| Metric | Value |
|--------|-------|
| Hit Rate@1 | 83.3% |
| Hit Rate@3 | 95.8% |
| Hit Rate@5 | 100.0% |
| Hit Rate@8 | 100.0% |
| MRR@8 | 0.892 |
| Latency (mean) | 99.6ms |
| Latency (p95) | 178.7ms |

## By Language

| Language | Queries | Hit@1 | Hit@8 |
|----------|---------|-------|-------|
| TR | 16 | 81.2% | 100.0% |
| EN | 8 | 87.5% | 100.0% |

## Per-Query Results

| # | Lang | Episode | Question | Rank | Hit@1 | Hit@3 | Hit@5 | Distance | Latency |
|---|------|---------|----------|------|-------|-------|-------|----------|---------|
| 1 | TR | ChatGPT, AI, Prompt Engineering | ChatGPT ve prompt engineering hakkında neler konuşuldu? | 1 | ✓ | ✓ | ✓ | 0.3703 | 1078.9ms |
| 2 | TR | ChatGPT, AI, Prompt Engineering | Yapay zeka ile kod yazmak ve öğrencilere kullandırmak | 1 | ✓ | ✓ | ✓ | 0.2159 | 104.1ms |
| 3 | EN | ChatGPT, AI, Prompt Engineering | AI code generation and teaching students | 1 | ✓ | ✓ | ✓ | 0.2443 | 178.7ms |
| 4 | TR | Elektronik ve Müzik Hobileri | elektrik gitar pedal ve elektronik hobiler | 1 | ✓ | ✓ | ✓ | 0.3023 | 147.8ms |
| 5 | TR | Elektronik ve Müzik Hobileri | müzik ekipmanları ve ses düzeni | 1 | ✓ | ✓ | ✓ | 0.3712 | 148.6ms |
| 6 | EN | Elektronik ve Müzik Hobileri | guitar pedals and electronics hobby | 1 | ✓ | ✓ | ✓ | 0.2866 | 12.3ms |
| 7 | TR | JSDoc, Architecture Patterns | yazılım mimarisi hexagonal onion clean architecture | 1 | ✓ | ✓ | ✓ | 0.5365 | 160.0ms |
| 8 | TR | JSDoc, Architecture Patterns | JSDoc kullanımı ve faydaları | 3 | ✗ | ✓ | ✓ | 0.5487 | 11.4ms |
| 9 | EN | JSDoc, Architecture Patterns | software architecture layered hexagonal design patterns | 1 | ✓ | ✓ | ✓ | 0.5043 | 7.3ms |
| 10 | TR | ADHD, Kişisel Gelişim | ADHD ile çalışmak ve planlı yaşam | 1 | ✓ | ✓ | ✓ | 0.2792 | 5.7ms |
| 11 | TR | ADHD, Kişisel Gelişim | uyku düzeni ve kişisel verimlilik | 1 | ✓ | ✓ | ✓ | 0.2505 | 6.4ms |
| 12 | EN | ADHD, Kişisel Gelişim | ADHD productivity and personal development in software | 1 | ✓ | ✓ | ✓ | 0.3845 | 145.1ms |
| 13 | TR | Kütüphane Yazımı, Composition API | Vue Composition API ve Options API karşılaştırması | 1 | ✓ | ✓ | ✓ | 0.4091 | 155.0ms |
| 14 | TR | Kütüphane Yazımı, Composition API | JavaScript kütüphanesi nasıl yazılır | 4 | ✗ | ✗ | ✓ | 0.4251 | 8.6ms |
| 15 | EN | Kütüphane Yazımı, Composition API | how to build a JavaScript library composition vs option… | 2 | ✗ | ✓ | ✓ | 0.4774 | 8.5ms |
| 16 | TR | Sabancı, Global Ekonomi | global ekonomi ve para birimleri arasındaki fark | 1 | ✓ | ✓ | ✓ | 0.1651 | 5.9ms |
| 17 | TR | Sabancı, Global Ekonomi | Sabancı üniversitesi yazılım mühendisliği deneyimi | 1 | ✓ | ✓ | ✓ | 0.3277 | 153.4ms |
| 18 | EN | Sabancı, Global Ekonomi | women in software engineering and global economy | 1 | ✓ | ✓ | ✓ | 0.331 | 9.5ms |
| 19 | TR | Dolandırıcılık, Software Testing | yazılım sektöründe dolandırıcılık ve sahtecilik | 1 | ✓ | ✓ | ✓ | 0.4473 | 8.6ms |
| 20 | TR | Dolandırıcılık, Software Testing | software testing önemi ve test yazma | 3 | ✗ | ✓ | ✓ | 0.4535 | 7.6ms |
| 21 | EN | Dolandırıcılık, Software Testing | software scams fraud and testing practices | 1 | ✓ | ✓ | ✓ | 0.5114 | 6.3ms |
| 22 | TR | İşten Çıkarmalar, Yöneticilik | işten çıkarmalar neden oluyor ve nasıl önlenir | 1 | ✓ | ✓ | ✓ | 0.2475 | 7.2ms |
| 23 | TR | İşten Çıkarmalar, Yöneticilik | iyi yönetici nasıl olunur liderlik | 1 | ✓ | ✓ | ✓ | 0.2215 | 6.4ms |
| 24 | EN | İşten Çıkarmalar, Yöneticilik | tech layoffs and management unit of work pattern | 1 | ✓ | ✓ | ✓ | 0.3858 | 6.9ms |

## Misses

No misses — all queries found expected source in top 8.