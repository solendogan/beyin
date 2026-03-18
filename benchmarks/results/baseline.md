# Retrieval Benchmark — baseline

**Date:** 2026-03-18 07:27  
**Pack:** armag-2  
**Embedding model:** all-MiniLM-L6-v2  
**n_results:** 8  
**Queries:** 24 (16 Turkish, 8 English)  
**Description:** Baseline: all-MiniLM-L6-v2, no reranking, n=8  

## Summary

| Metric | Value |
|--------|-------|
| Hit Rate@1 | 62.5% |
| Hit Rate@3 | 75.0% |
| Hit Rate@5 | 83.3% |
| Hit Rate@8 | 91.7% |
| MRR@8 | 0.705 |
| Latency (mean) | 16.8ms |
| Latency (p95) | 55.5ms |

## By Language

| Language | Queries | Hit@1 | Hit@8 |
|----------|---------|-------|-------|
| TR | 16 | 62.5% | 87.5% |
| EN | 8 | 62.5% | 100.0% |

## Per-Query Results

| # | Lang | Episode | Question | Rank | Hit@1 | Hit@3 | Hit@5 | Distance | Latency |
|---|------|---------|----------|------|-------|-------|-------|----------|---------|
| 1 | TR | ChatGPT, AI, Prompt Engineering | ChatGPT ve prompt engineering hakkında neler konuşuldu? | 4 | ✗ | ✗ | ✓ | 0.6433 | 64.4ms |
| 2 | TR | ChatGPT, AI, Prompt Engineering | Yapay zeka ile kod yazmak ve öğrencilere kullandırmak | 1 | ✓ | ✓ | ✓ | 0.5198 | 19.0ms |
| 3 | EN | ChatGPT, AI, Prompt Engineering | AI code generation and teaching students | 1 | ✓ | ✓ | ✓ | 1.2267 | 20.3ms |
| 4 | TR | Elektronik ve Müzik Hobileri | elektrik gitar pedal ve elektronik hobiler | 1 | ✓ | ✓ | ✓ | 0.676 | 17.6ms |
| 5 | TR | Elektronik ve Müzik Hobileri | müzik ekipmanları ve ses düzeni | **MISS** | ✗ | ✗ | ✗ | 0.6059 | 18.5ms |
| 6 | EN | Elektronik ve Müzik Hobileri | guitar pedals and electronics hobby | 1 | ✓ | ✓ | ✓ | 1.0633 | 6.6ms |
| 7 | TR | JSDoc, Architecture Patterns | yazılım mimarisi hexagonal onion clean architecture | 1 | ✓ | ✓ | ✓ | 0.9695 | 6.6ms |
| 8 | TR | JSDoc, Architecture Patterns | JSDoc kullanımı ve faydaları | 8 | ✗ | ✗ | ✗ | 0.5652 | 19.5ms |
| 9 | EN | JSDoc, Architecture Patterns | software architecture layered hexagonal design patterns | 3 | ✗ | ✓ | ✓ | 1.5933 | 18.5ms |
| 10 | TR | ADHD, Kişisel Gelişim | ADHD ile çalışmak ve planlı yaşam | 1 | ✓ | ✓ | ✓ | 0.422 | 6.5ms |
| 11 | TR | ADHD, Kişisel Gelişim | uyku düzeni ve kişisel verimlilik | 2 | ✗ | ✓ | ✓ | 0.8891 | 6.2ms |
| 12 | EN | ADHD, Kişisel Gelişim | ADHD productivity and personal development in software | 1 | ✓ | ✓ | ✓ | 1.1547 | 6.6ms |
| 13 | TR | Kütüphane Yazımı, Composition API | Vue Composition API ve Options API karşılaştırması | 1 | ✓ | ✓ | ✓ | 0.6741 | 16.2ms |
| 14 | TR | Kütüphane Yazımı, Composition API | JavaScript kütüphanesi nasıl yazılır | 6 | ✗ | ✗ | ✗ | 0.38 | 5.9ms |
| 15 | EN | Kütüphane Yazımı, Composition API | how to build a JavaScript library composition vs option… | 1 | ✓ | ✓ | ✓ | 1.3087 | 55.5ms |
| 16 | TR | Sabancı, Global Ekonomi | global ekonomi ve para birimleri arasındaki fark | 1 | ✓ | ✓ | ✓ | 0.3662 | 7.4ms |
| 17 | TR | Sabancı, Global Ekonomi | Sabancı üniversitesi yazılım mühendisliği deneyimi | 1 | ✓ | ✓ | ✓ | 0.4719 | 18.7ms |
| 18 | EN | Sabancı, Global Ekonomi | women in software engineering and global economy | 5 | ✗ | ✗ | ✓ | 1.2927 | 18.0ms |
| 19 | TR | Dolandırıcılık, Software Testing | yazılım sektöründe dolandırıcılık ve sahtecilik | **MISS** | ✗ | ✗ | ✗ | 0.4766 | 17.1ms |
| 20 | TR | Dolandırıcılık, Software Testing | software testing önemi ve test yazma | 1 | ✓ | ✓ | ✓ | 1.0999 | 18.5ms |
| 21 | EN | Dolandırıcılık, Software Testing | software scams fraud and testing practices | 3 | ✗ | ✓ | ✓ | 1.5387 | 7.0ms |
| 22 | TR | İşten Çıkarmalar, Yöneticilik | işten çıkarmalar neden oluyor ve nasıl önlenir | 1 | ✓ | ✓ | ✓ | 0.4772 | 16.1ms |
| 23 | TR | İşten Çıkarmalar, Yöneticilik | iyi yönetici nasıl olunur liderlik | 1 | ✓ | ✓ | ✓ | 0.6217 | 6.5ms |
| 24 | EN | İşten Çıkarmalar, Yöneticilik | tech layoffs and management unit of work pattern | 1 | ✓ | ✓ | ✓ | 1.1447 | 7.2ms |

## Misses

- **[TR]** `müzik ekipmanları ve ses düzeni`
  - Expected: Elektronik ve Müzik Hobileri
  - Top result: Kişisel Gelişim ve Yaşam Dengesi: ADHD, Az Uyumak, Plansız Yaşamak, Emeklilik ve Dahası

- **[TR]** `yazılım sektöründe dolandırıcılık ve sahtecilik`
  - Expected: Dolandırıcılık, Software Testing
  - Top result: ChatGPT, AI, Prompt engineering
