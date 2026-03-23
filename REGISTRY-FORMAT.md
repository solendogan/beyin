# Brainpack Registry Format

This file describes the final registry pack format used in the repository.

It is mainly for maintainers or advanced contributors working directly with pack YAML files. If you are submitting a pack through the issue form, use [CONTRIBUTING.md](CONTRIBUTING.md) instead.

A pack is a single `pack.yaml` file. Source types are auto-detected from the URL — no need to specify them manually.

---

## Example

```yaml
id: ux-planet
name: UX Planet
version: 1.0.0
description: Articles and learning sources focused on UX, product thinking, and interface design.
created: 2026-03-16
updated: 2026-03-16

tags: [design, ux, product, ui]

contributors:
  - your github username

sources:
  - https://uxplanet.org/
  - https://uxplanet.org/example-article
  - https://youtube.com/watch?v=example
```

---

## Required Fields

| Field | Description |
|---|---|
| `id` | Unique identifier. Lowercase, hyphenated, stable over time. |
| `name` | Human-readable display name. |
| `version` | Semantic version (`1.0.0`). |
| `description` | One or two sentences explaining what this pack is about. |
| `created` | Date the pack was first published (`YYYY-MM-DD`). |
| `updated` | Date the pack was last modified (`YYYY-MM-DD`). |
| `contributors` | List of GitHub usernames who have contributed. |
| `sources` | List of URLs to include. |

---

## Sources

Sources are plain URLs. Brainpack auto-detects the type:

- YouTube video, playlist, or channel URLs → `youtube`
- RSS feed URLs → `podcast`
- Article or website URLs → `article`

No need to specify the type manually.

---

## Versioning

Use semantic versioning:

- `1.0.0` → first published version
- `1.1.0` → new sources added
- `1.1.1` → metadata fix, typo, description update
- `2.0.0` → major restructuring or breaking change

---

## Registry Structure

The registry is a flat directory of YAML files:

```text
packs/
  mobile-app-marketing.yaml
  design-fundamentals.yaml
  math-notes.yaml
```

One file per pack. No subfolders needed.
