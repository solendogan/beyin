# Retrieval Benchmark — normalized-cosine-hard

**Date:** 2026-03-18 08:29  
**Pack:** armag-2  
**Embedding model:** paraphrase-multilingual-mpnet-base-v2  
**n_results:** 8  
**Queries:** 24 (16 Turkish, 8 English)  
**Description:** Hard dataset: multilingual-mpnet + normalized embeddings + cosine distance  

## Summary

| Metric | Value |
|--------|-------|
| Hit Rate@1 | 83.3% |
| Hit Rate@3 | 87.5% |
| Hit Rate@5 | 95.8% |
| Hit Rate@8 | 95.8% |
| MRR@8 | 0.864 |
| Latency (mean) | 20.6ms |
| Latency (p95) | 34.3ms |

## By Language

| Language | Queries | Hit@1 | Hit@8 |
|----------|---------|-------|-------|
| TR | 16 | 81.2% | 100.0% |
| EN | 8 | 87.5% | 87.5% |

## Per-Query Results

| # | Lang | Episode | Question | Rank | Hit@1 | Hit@3 | Hit@5 | Distance | Latency |
|---|------|---------|----------|------|-------|-------|-------|----------|---------|
| 1 | TR | Elektronik ve Müzik Hobileri | Roland GK3 ve Boss GM800 nasıl bağlanır | 1 | ✓ | ✓ | ✓ | 0.2196 | 105.1ms |
| 2 | TR | Elektronik ve Müzik Hobileri | MIDI bluetooth wireless gitar pedal bağlantısı | 1 | ✓ | ✓ | ✓ | 0.1326 | 33.1ms |
| 3 | EN | Elektronik ve Müzik Hobileri | Roland GK3 guitar synthesizer MIDI wireless setup | 1 | ✓ | ✓ | ✓ | 0.2618 | 34.3ms |
| 4 | TR | Elektronik ve Müzik Hobileri | Fender Stratocaster modifikasyonu ve pedallar | 1 | ✓ | ✓ | ✓ | 0.4576 | 32.8ms |
| 5 | TR | ChatGPT, AI, Prompt Engineering | GitHub Copilot kod yazma deneyimi | 1 | ✓ | ✓ | ✓ | 0.3297 | 29.0ms |
| 6 | TR | ChatGPT, AI, Prompt Engineering | OpenAI GPT-4 prompt engineering ipuçları | 1 | ✓ | ✓ | ✓ | 0.5194 | 12.0ms |
| 7 | EN | ChatGPT, AI, Prompt Engineering | GitHub Copilot vs ChatGPT for coding assistance | 1 | ✓ | ✓ | ✓ | 0.3042 | 29.8ms |
| 8 | TR | Kütüphane Yazımı, Composition API | Vue Composition API reactive ref ve computed kullanımı | 1 | ✓ | ✓ | ✓ | 0.3747 | 13.4ms |
| 9 | TR | Kütüphane Yazımı, Composition API | MongoDB ve SQL veritabanı karşılaştırması | 1 | ✓ | ✓ | ✓ | 0.4745 | 12.1ms |
| 10 | EN | Kütüphane Yazımı, Composition API | JavaScript library publishing npm package bundling | 1 | ✓ | ✓ | ✓ | 0.6498 | 8.0ms |
| 11 | TR | Dolandırıcılık, Software Testing | Udemy kurs kalitesi ve yazılım eğitimi | 3 | ✗ | ✓ | ✓ | 0.4995 | 8.0ms |
| 12 | TR | Dolandırıcılık, Software Testing | PHP yazılımcı iş piyasasındaki yeri | 5 | ✗ | ✗ | ✓ | 0.5405 | 7.6ms |
| 13 | EN | Dolandırıcılık, Software Testing | unit testing TDD test driven development practices | **MISS** | ✗ | ✗ | ✗ | 0.5609 | 8.0ms |
| 14 | TR | JSDoc, Architecture Patterns | TypeScript tip sistemi ve JSDoc karşılaştırması | 1 | ✓ | ✓ | ✓ | 0.2268 | 11.5ms |
| 15 | TR | JSDoc, Architecture Patterns | hexagonal architecture domain driven design uygulama | 1 | ✓ | ✓ | ✓ | 0.3966 | 9.8ms |
| 16 | EN | JSDoc, Architecture Patterns | JSDoc type annotations versus TypeScript tradeoffs | 1 | ✓ | ✓ | ✓ | 0.3479 | 8.3ms |
| 17 | TR | İşten Çıkarmalar, Yöneticilik | Unit of Work ve Repository pattern implementasyonu | 1 | ✓ | ✓ | ✓ | 0.5085 | 7.4ms |
| 18 | TR | İşten Çıkarmalar, Yöneticilik | AstroJS ile modern web geliştirme | 1 | ✓ | ✓ | ✓ | 0.3854 | 26.3ms |
| 19 | EN | İşten Çıkarmalar, Yöneticilik | REST API design patterns best practices backend | 1 | ✓ | ✓ | ✓ | 0.4795 | 10.8ms |
| 20 | TR | ADHD, Kişisel Gelişim | CBT kognitif davranışçı terapi ADHD yönetimi | 1 | ✓ | ✓ | ✓ | 0.4327 | 8.0ms |
| 21 | EN | ADHD, Kişisel Gelişim | cognitive behavioral therapy CBT productivity ADHD | 1 | ✓ | ✓ | ✓ | 0.4116 | 8.6ms |
| 22 | TR | Sabancı, Global Ekonomi | Sabancı üniversitesi CS301 CS308 yazılım dersleri | 1 | ✓ | ✓ | ✓ | 0.4402 | 29.3ms |
| 23 | TR | Sabancı, Global Ekonomi | dolar kur farkı ve yazılımcı maaşları Türkiye | 5 | ✗ | ✗ | ✓ | 0.3846 | 10.3ms |
| 24 | EN | Sabancı, Global Ekonomi | computer science university education Turkey software e… | 1 | ✓ | ✓ | ✓ | 0.4413 | 30.5ms |

## Misses

- **[EN]** `unit testing TDD test driven development practices`
  - Expected: Dolandırıcılık, Software Testing
  - Top result: ChatGPT, AI, Prompt engineering
