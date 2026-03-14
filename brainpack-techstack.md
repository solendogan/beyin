# Brainpack Tech Stack and Product Direction

Brainpack is a local-first retrieval product with two supported ways to use it:

- `Use with agent` is the recommended path
- `Use with local model` is the standalone path

The important technical distinction is simple:

- agent mode uses Brainpack as a same-machine evidence service
- local mode uses the same retrieval layer plus a local answer model

## Current Product Framing

### Use with agent

Recommended for Codex, Claude Code, OpenClaw, and other same-machine agent setups.

Brainpack does not need to be the final-answer writer in this path. It builds the pack, retrieves the evidence, and exposes that evidence through the local MCP server. The agent synthesizes the final answer.

First run order:

1. Connect agent
   Launch the shipped local server command:

   ```bash
   brainpack mcp-server
   ```

2. Set up pack
   Create a pack or install one:

   ```bash
   brainpack create
   brainpack add <path-or-url-or-id>
   ```

3. Build
   Build the pack before the agent starts asking for evidence:

   ```bash
   brainpack build <pack>
   ```

### Use with local model

Standalone path for users who want Brainpack to answer directly with a local runtime.

This path keeps `brainpack query` and `brainpack chat` as normal product commands, not as a fallback. The retrieval/index layer is the same; the final answer comes from the configured local model.

First run order:

1. Install local runtime
   Install the local model runtime you want to use.

2. Run doctor
   Check local readiness before building:

   ```bash
   brainpack doctor <pack>
   ```

3. Create/add pack
   Create a new pack or install one:

   ```bash
   brainpack create
   brainpack add <path-or-url-or-id>
   ```

4. Build
   Build the pack before running local questions:

   ```bash
   brainpack build <pack>
   ```

After build, the standalone commands are:

```bash
brainpack query <pack> "question"
brainpack chat <pack> "question"
```

## Shipped Architecture

### CLI framework

- Python 3.11+
- `typer` for the command surface
- `uv` for dependency and environment management

### Source ingestion

- `yt-dlp` for YouTube audio retrieval
- `feedparser` for podcast RSS ingestion
- `trafilatura` for article extraction

### Text preparation

- `nltk` for chunking support
- `sentence-transformers` for local embeddings

### Storage and retrieval

- `chromadb` for local vector storage
- local pack directories for config, transcripts, metadata, and build state

### Answer runtime

- local model runtime for standalone `query` and `chat`
- no remote service requirement for the core product flow

### Agent integration

- local MCP server shipped today through `brainpack mcp-server`
- stdio transport for same-machine agent launches
- retrieval-first direction for agent usage: Brainpack returns evidence, agent writes the answer

## Build Pipeline

Both modes share the same build pipeline:

1. ingest sources
2. extract or transcribe text
3. chunk content
4. embed chunks
5. write vectors and metadata locally
6. retrieve evidence at question time

Only the final step differs by mode:

- agent mode returns evidence to the agent
- local mode returns evidence and asks the configured model for the answer

## Local Storage Shape

Example pack layout:

```text
~/.brainpacks/
  armagan-amcalar/
    pack.yaml
    audio/
    transcripts/
    chroma/
    meta.json
```

That layout keeps Brainpack portable and local-first:

- users own the data
- rebuilds happen on the same machine
- pack definitions stay sharable without shipping derived content

## Command Map

Shared lifecycle commands:

```bash
brainpack create
brainpack add <path-or-url-or-id>
brainpack build <pack>
brainpack list
brainpack status <pack>
brainpack doctor <pack>
```

Recommended agent command:

```bash
brainpack mcp-server
```

Standalone local-mode commands:

```bash
brainpack query <pack> "question"
brainpack chat <pack> "question"
```

## Product Constraints

Brainpack is intentionally optimized for:

- local-first retrieval
- same-machine agent onboarding
- explicit pack lifecycle commands
- sharable pack manifests instead of hosted knowledge storage

Brainpack is intentionally not using:

- remote onboarding stories
- attach-style agent commands
- query-first first-run guidance
- future-server concepts as the primary integration story

## Decision Summary

- `Use with agent` is the default recommendation because the product value is retrieval and evidence quality for an external same-machine agent.
- `Use with local model` stays fully supported as the standalone route for users who want Brainpack to answer directly.
- The docs should always preserve the same first-run order in both modes so CLI help, markdown docs, and onboarding cannot drift apart.
