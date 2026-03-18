# Retrieval Benchmark — medium-whisper-multilingual

**Date:** 2026-03-18 07:54  
**Pack:** armag-2  
**Embedding model:** paraphrase-multilingual-mpnet-base-v2  
**n_results:** 8  
**Queries:** 24 (16 Turkish, 8 English)  
**Description:** whisper-medium transcripts + paraphrase-multilingual-mpnet-base-v2 embeddings  

## Summary

| Metric | Value |
|--------|-------|
| Hit Rate@1 | 83.3% |
| Hit Rate@3 | 91.7% |
| Hit Rate@5 | 95.8% |
| Hit Rate@8 | 100.0% |
| MRR@8 | 0.885 |
| Latency (mean) | 19.5ms |
| Latency (p95) | 39.7ms |

## By Language

| Language | Queries | Hit@1 | Hit@8 |
|----------|---------|-------|-------|
| TR | 16 | 87.5% | 100.0% |
| EN | 8 | 75.0% | 100.0% |

## Per-Query Results

| # | Lang | Episode | Question | Rank | Hit@1 | Hit@3 | Hit@5 | Distance | Latency |
|---|------|---------|----------|------|-------|-------|-------|----------|---------|
| 1 | TR | ChatGPT, AI, Prompt Engineering | ChatGPT ve prompt engineering hakkında neler konuşuldu? | 1 | ✓ | ✓ | ✓ | 4.0135 | 88.3ms |
| 2 | TR | ChatGPT, AI, Prompt Engineering | Yapay zeka ile kod yazmak ve öğrencilere kullandırmak | 1 | ✓ | ✓ | ✓ | 4.45 | 29.8ms |
| 3 | EN | ChatGPT, AI, Prompt Engineering | AI code generation and teaching students | 1 | ✓ | ✓ | ✓ | 6.087 | 25.8ms |
| 4 | TR | Elektronik ve Müzik Hobileri | elektrik gitar pedal ve elektronik hobiler | 1 | ✓ | ✓ | ✓ | 5.211 | 29.8ms |
| 5 | TR | Elektronik ve Müzik Hobileri | müzik ekipmanları ve ses düzeni | 1 | ✓ | ✓ | ✓ | 4.0638 | 31.1ms |
| 6 | EN | Elektronik ve Müzik Hobileri | guitar pedals and electronics hobby | 1 | ✓ | ✓ | ✓ | 5.5041 | 13.4ms |
| 7 | TR | JSDoc, Architecture Patterns | yazılım mimarisi hexagonal onion clean architecture | 1 | ✓ | ✓ | ✓ | 6.9915 | 39.7ms |
| 8 | TR | JSDoc, Architecture Patterns | JSDoc kullanımı ve faydaları | 1 | ✓ | ✓ | ✓ | 5.2399 | 8.6ms |
| 9 | EN | JSDoc, Architecture Patterns | software architecture layered hexagonal design patterns | 1 | ✓ | ✓ | ✓ | 6.2432 | 8.4ms |
| 10 | TR | ADHD, Kişisel Gelişim | ADHD ile çalışmak ve planlı yaşam | 1 | ✓ | ✓ | ✓ | 3.8922 | 7.4ms |
| 11 | TR | ADHD, Kişisel Gelişim | uyku düzeni ve kişisel verimlilik | 1 | ✓ | ✓ | ✓ | 4.8257 | 6.9ms |
| 12 | EN | ADHD, Kişisel Gelişim | ADHD productivity and personal development in software | 1 | ✓ | ✓ | ✓ | 5.7004 | 31.4ms |
| 13 | TR | Kütüphane Yazımı, Composition API | Vue Composition API ve Options API karşılaştırması | 1 | ✓ | ✓ | ✓ | 4.2522 | 31.2ms |
| 14 | TR | Kütüphane Yazımı, Composition API | JavaScript kütüphanesi nasıl yazılır | 4 | ✗ | ✗ | ✓ | 5.7494 | 10.3ms |
| 15 | EN | Kütüphane Yazımı, Composition API | how to build a JavaScript library composition vs option… | 1 | ✓ | ✓ | ✓ | 6.106 | 9.7ms |
| 16 | TR | Sabancı, Global Ekonomi | global ekonomi ve para birimleri arasındaki fark | 1 | ✓ | ✓ | ✓ | 2.6979 | 7.3ms |
| 17 | TR | Sabancı, Global Ekonomi | Sabancı üniversitesi yazılım mühendisliği deneyimi | 1 | ✓ | ✓ | ✓ | 4.424 | 31.5ms |
| 18 | EN | Sabancı, Global Ekonomi | women in software engineering and global economy | 6 | ✗ | ✗ | ✗ | 7.7987 | 9.9ms |
| 19 | TR | Dolandırıcılık, Software Testing | yazılım sektöründe dolandırıcılık ve sahtecilik | 3 | ✗ | ✓ | ✓ | 6.8361 | 10.6ms |
| 20 | TR | Dolandırıcılık, Software Testing | software testing önemi ve test yazma | 1 | ✓ | ✓ | ✓ | 6.751 | 7.3ms |
| 21 | EN | Dolandırıcılık, Software Testing | software scams fraud and testing practices | 2 | ✗ | ✓ | ✓ | 9.118 | 7.5ms |
| 22 | TR | İşten Çıkarmalar, Yöneticilik | işten çıkarmalar neden oluyor ve nasıl önlenir | 1 | ✓ | ✓ | ✓ | 3.0571 | 7.6ms |
| 23 | TR | İşten Çıkarmalar, Yöneticilik | iyi yönetici nasıl olunur liderlik | 1 | ✓ | ✓ | ✓ | 3.1061 | 6.8ms |
| 24 | EN | İşten Çıkarmalar, Yöneticilik | tech layoffs and management unit of work pattern | 1 | ✓ | ✓ | ✓ | 6.7309 | 8.2ms |

## Misses

No misses — all queries found expected source in top 8.