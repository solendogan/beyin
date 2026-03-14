# Brainpack

Turn trusted creators into local expert memory.

Brainpack turns long-form content such as YouTube channels, podcast feeds, and articles into searchable packs on your own machine. It keeps the retrieval layer local, builds the index once, and lets you either hand the evidence to an agent or ask questions directly with a local model.

## What Brainpack Does

Brainpack ingests source material, extracts or transcribes the text, chunks it, embeds it, and stores the results locally for retrieval. The product is local-first:

- source data is processed on your machine
- the vector index lives on your machine
- packs stay portable because the sharable artifact is the pack definition, not hosted data

The goal is simple:

> Stop re-watching and start asking.

## Two Ways To Use Brainpack

Brainpack is a two-path product. The recommended path is to use Brainpack with an agent running on the same machine. The standalone path is to use Brainpack with a local model and ask questions directly yourself.

### Use with agent

Recommended for Codex, Claude Code, OpenClaw, or any same-machine agent setup.

In this path, Brainpack finds evidence. Your agent reads that evidence and writes the final answer.

First run order:

1. Connect agent
   Start the local MCP server so your agent can call Brainpack on the same machine:

   ```bash
   brainpack mcp-server
   ```

2. Set up pack
   Create a new pack or install an existing one:

   ```bash
   brainpack create
   brainpack add <path-or-url-or-id>
   ```

3. Build
   Build the pack so retrieval data exists before the agent asks for evidence:

   ```bash
   brainpack build <pack>
   ```

After that, your agent can inspect packs, run doctor checks, and retrieve evidence through the local MCP connection.

### Use with local model

Standalone path for users who want Brainpack to stay fully local and answer through their own runtime.

In this path, `brainpack query` and `brainpack chat` stay first-class commands. You still build the same local retrieval layer; the difference is that Brainpack also calls your configured answer model directly.

First run order:

1. Install local runtime
   Install and start the local model runtime you want to use, such as Ollama.

2. Run doctor
   Verify local prerequisites before you invest time in a build:

   ```bash
   brainpack doctor <pack>
   ```

3. Create/add pack
   Make a new pack or install one:

   ```bash
   brainpack create
   brainpack add <path-or-url-or-id>
   ```

4. Build
   Build the pack before you query or chat with it:

   ```bash
   brainpack build <pack>
   ```

Once the pack is built, use either of these standalone commands:

```bash
brainpack query <pack> "question"
brainpack chat <pack> "question"
```

## What A Pack Contains

A pack is a curated source bundle plus the local artifacts Brainpack builds from it.

Typical inputs:

- YouTube channels or playlists
- podcast RSS feeds
- articles and blog posts

Typical local build outputs:

- transcripts or extracted article text
- chunks
- embeddings
- local vector index files
- build metadata

The shared piece is the pack definition. The heavy derived data stays local.

## Local-First Architecture

Brainpack keeps the product lightweight and legally cleaner by avoiding a hosted transcript or vector service.

Example local structure:

```text
~/.brainpacks/
  software-architecture-tr/
    pack.yaml
    audio/
    transcripts/
    chroma/
    meta.json
```

That design keeps Brainpack portable:

- move packs between machines by moving files
- rebuild locally when sources change
- share source manifests without sharing copyrighted derived data

## Retrieval Model

The retrieval pipeline is the same in both modes:

1. collect source text
2. chunk content into retrieval units
3. embed chunks locally
4. store vectors in a local index
5. retrieve the best evidence for a question

The difference is what happens after retrieval:

- agent mode: Brainpack returns evidence to an agent on the same machine
- local mode: Brainpack retrieves evidence and also asks the configured model for the final answer

## CLI Overview

Pack lifecycle commands:

```bash
brainpack create
brainpack add <path-or-url-or-id>
brainpack build <pack>
brainpack list
brainpack status <pack>
brainpack doctor <pack>
```

Mode-specific commands:

```bash
brainpack mcp-server
brainpack query <pack> "question"
brainpack chat <pack> "question"
```

## Why This Product Shape

Long-form content is valuable but hard to reuse:

- the right episode is hard to find
- the right minute inside the episode is harder
- the same material gets re-watched instead of retrieved

Brainpack turns that backlog into a reusable memory layer. The recommended product story is not "Brainpack is a chatbot." It is:

- Brainpack builds the memory locally
- Brainpack retrieves the evidence locally
- your agent or local model uses that evidence to answer

## Product Direction

Brainpack is intentionally focused on:

- local-first indexing and retrieval
- same-machine agent workflows through `brainpack mcp-server`
- standalone local answering through `query` and `chat`
- sharable pack definitions instead of hosted knowledge storage

It is intentionally not focused on:

- remote MCP hosting
- service-first deployment
- attach-style integrations
- turning the onboarding story back into a generic query-first flow
