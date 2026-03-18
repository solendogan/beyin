# Retrieval Benchmark — hard-small-whisper

**Date:** 2026-03-18 08:08  
**Pack:** armag-2  
**Embedding model:** paraphrase-multilingual-mpnet-base-v2  
**n_results:** 8  
**Queries:** 24 (16 Turkish, 8 English)  
**Description:** Hard queries: whisper-small + paraphrase-multilingual-mpnet-base-v2  

## Summary

| Metric | Value |
|--------|-------|
| Hit Rate@1 | 79.2% |
| Hit Rate@3 | 91.7% |
| Hit Rate@5 | 91.7% |
| Hit Rate@8 | 95.8% |
| MRR@8 | 0.854 |
| Latency (mean) | 19.2ms |
| Latency (p95) | 34.6ms |

## By Language

| Language | Queries | Hit@1 | Hit@8 |
|----------|---------|-------|-------|
| TR | 16 | 81.2% | 100.0% |
| EN | 8 | 75.0% | 87.5% |

## Per-Query Results

| # | Lang | Episode | Question | Rank | Hit@1 | Hit@3 | Hit@5 | Distance | Latency |
|---|------|---------|----------|------|-------|-------|-------|----------|---------|
| 1 | TR | Elektronik ve Müzik Hobileri | Roland GK3 ve Boss GM800 nasıl bağlanır | 1 | ✓ | ✓ | ✓ | 3.1327 | 82.6ms |
| 2 | TR | Elektronik ve Müzik Hobileri | MIDI bluetooth wireless gitar pedal bağlantısı | 1 | ✓ | ✓ | ✓ | 2.0827 | 30.2ms |
| 3 | EN | Elektronik ve Müzik Hobileri | Roland GK3 guitar synthesizer MIDI wireless setup | 1 | ✓ | ✓ | ✓ | 3.9641 | 31.1ms |
| 4 | TR | Elektronik ve Müzik Hobileri | Fender Stratocaster modifikasyonu ve pedallar | 1 | ✓ | ✓ | ✓ | 6.3604 | 33.8ms |
| 5 | TR | ChatGPT, AI, Prompt Engineering | GitHub Copilot kod yazma deneyimi | 1 | ✓ | ✓ | ✓ | 3.8081 | 30.7ms |
| 6 | TR | ChatGPT, AI, Prompt Engineering | OpenAI GPT-4 prompt engineering ipuçları | 1 | ✓ | ✓ | ✓ | 6.4121 | 15.1ms |
| 7 | EN | ChatGPT, AI, Prompt Engineering | GitHub Copilot vs ChatGPT for coding assistance | 1 | ✓ | ✓ | ✓ | 3.7534 | 34.6ms |
| 8 | TR | Kütüphane Yazımı, Composition API | Vue Composition API reactive ref ve computed kullanımı | 1 | ✓ | ✓ | ✓ | 4.4791 | 12.2ms |
| 9 | TR | Kütüphane Yazımı, Composition API | MongoDB ve SQL veritabanı karşılaştırması | 1 | ✓ | ✓ | ✓ | 5.9189 | 8.4ms |
| 10 | EN | Kütüphane Yazımı, Composition API | JavaScript library publishing npm package bundling | 2 | ✗ | ✓ | ✓ | 8.8873 | 7.6ms |
| 11 | TR | Dolandırıcılık, Software Testing | Udemy kurs kalitesi ve yazılım eğitimi | 2 | ✗ | ✓ | ✓ | 6.2387 | 8.7ms |
| 12 | TR | Dolandırıcılık, Software Testing | PHP yazılımcı iş piyasasındaki yeri | 3 | ✗ | ✓ | ✓ | 7.7238 | 8.3ms |
| 13 | EN | Dolandırıcılık, Software Testing | unit testing TDD test driven development practices | **MISS** | ✗ | ✗ | ✗ | 8.5042 | 8.5ms |
| 14 | TR | JSDoc, Architecture Patterns | TypeScript tip sistemi ve JSDoc karşılaştırması | 1 | ✓ | ✓ | ✓ | 3.3147 | 9.1ms |
| 15 | TR | JSDoc, Architecture Patterns | hexagonal architecture domain driven design uygulama | 1 | ✓ | ✓ | ✓ | 5.6561 | 9.1ms |
| 16 | EN | JSDoc, Architecture Patterns | JSDoc type annotations versus TypeScript tradeoffs | 1 | ✓ | ✓ | ✓ | 5.0074 | 9.7ms |
| 17 | TR | İşten Çıkarmalar, Yöneticilik | Unit of Work ve Repository pattern implementasyonu | 1 | ✓ | ✓ | ✓ | 6.2248 | 8.1ms |
| 18 | TR | İşten Çıkarmalar, Yöneticilik | AstroJS ile modern web geliştirme | 1 | ✓ | ✓ | ✓ | 5.4001 | 26.0ms |
| 19 | EN | İşten Çıkarmalar, Yöneticilik | REST API design patterns best practices backend | 1 | ✓ | ✓ | ✓ | 6.6075 | 8.3ms |
| 20 | TR | ADHD, Kişisel Gelişim | CBT kognitif davranışçı terapi ADHD yönetimi | 1 | ✓ | ✓ | ✓ | 6.6316 | 7.4ms |
| 21 | EN | ADHD, Kişisel Gelişim | cognitive behavioral therapy CBT productivity ADHD | 1 | ✓ | ✓ | ✓ | 6.5178 | 8.8ms |
| 22 | TR | Sabancı, Global Ekonomi | Sabancı üniversitesi CS301 CS308 yazılım dersleri | 1 | ✓ | ✓ | ✓ | 5.31 | 27.8ms |
| 23 | TR | Sabancı, Global Ekonomi | dolar kur farkı ve yazılımcı maaşları Türkiye | 6 | ✗ | ✗ | ✗ | 5.4727 | 8.6ms |
| 24 | EN | Sabancı, Global Ekonomi | computer science university education Turkey software e… | 1 | ✓ | ✓ | ✓ | 6.3744 | 26.4ms |

## Misses

- **[EN]** `unit testing TDD test driven development practices`
  - Expected: Dolandırıcılık, Software Testing
  - Top result: ChatGPT, AI, Prompt engineering
