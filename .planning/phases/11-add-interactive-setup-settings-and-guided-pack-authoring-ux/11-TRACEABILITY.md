# Phase 11 Traceability

## Requirements Covered

- `ONB-02`: Interactive setup and guided authoring stay aligned with the existing create/add/manage boundaries.
- `RUN-01`: Build now ingests narrow local text-like sources alongside remote article sources without broadening into a parser matrix.
- `RUN-02`: Build-time transcription defaults resolve deterministically as CLI flags, then pack config, then global settings, then fallback.
- `AUT-01`: Machine-safe JSON surfaces remain single-document and prompt-free after local-source support lands.
- `AUT-02`: Interactive-only behavior stays out of explicit command, JSON, and MCP paths.

## Locked Scope Decisions

- Supported local file ingestion stays intentionally narrow: `.txt`, `.md`, `.markdown`, `.rst`, `.html`, and `.htm`.
- `pack.yaml` remains import-only and belongs on `brainpack add`, not as a build source.
- Unsupported local files fail clearly instead of widening Brainpack into a general document parser or adding PDF support.

## Phase Coverage

- `11-01` introduced persisted machine-level settings and the initial setup seam.
- `11-02` added the interactive settings flow and kept machine-safe command paths prompt-free.
- `11-03` shipped the guided create/import/manage authoring seam and preserved the `add` boundary.
- `11-04` completed the end-to-end story by making authored local text-like paths buildable and by resolving one explicit build-default precedence path.
