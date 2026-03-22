<div align="center">

# Brainpack

**Turn YouTube videos, articles, podcasts, and local files into searchable knowledge packs. Then let your AI agent query them over MCP.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-6f42c1?style=for-the-badge)](https://modelcontextprotocol.io)

</div>

---

## What is Brainpack?

You follow creators. You save articles. You have local docs you never re-read.

Brainpack indexes all of that into a local, private knowledge pack. Your agent can then pull answers from those packs during normal conversation, without you having to paste context, summarize videos, or remember where you read something.

**The main workflow:**

1. Build a pack from your sources
2. Connect Brainpack to your agent via MCP
3. Ask your agent questions and it retrieves from your packs automatically

---

## MCP: The Main Way to Use Brainpack

> If you already use Claude Code, Codex, Cursor, or any other AI coding agent, this is the path. You do not need to learn any new commands.

Once Brainpack is connected as an MCP server, your agent can:

- create and manage packs
- add new sources (URLs, local files, YouTube videos)
- build and update packs
- retrieve relevant results in response to your questions

You just talk to your agent normally. It handles the rest.

---

## Quick Start

### Step 1: Install

```bash
pip install brainpack
```

Verify your setup:

```bash
brainpack check-deps
```

**Only needed for YouTube, audio, and video sources. Skip if you only use articles and local text:**

**yt-dlp** (any OS):
```bash
pip install yt-dlp
```

**ffmpeg:**
```bash
# macOS with Homebrew
brew install ffmpeg

# Linux
sudo apt install ffmpeg

# Windows
winget install ffmpeg
```

No Homebrew on macOS or winget not working? Download directly from [ffmpeg.org/download.html](https://ffmpeg.org/download.html).

---

### Step 2: Connect to your agent

You only need to do this once.

#### Claude Code

```bash
claude mcp add brainpack -- brainpack mcp-server
```

No config file editing needed, and **no need to keep a terminal open**. Claude Code launches and manages the server process automatically. Restart Claude Code and `brainpack` will appear in your MCP tools.

To make it available across all your projects:

```bash
claude mcp add --scope user brainpack -- brainpack mcp-server
```

#### Codex (OpenAI)

```bash
codex mcp add brainpack -- brainpack mcp-server
```

#### Cursor

Open or create `~/.cursor/mcp.json` and add:

```json
{
  "brainpack": {
    "command": "brainpack",
    "args": ["mcp-server"]
  }
}
```

Or go to Command Palette → **"View: Open MCP Settings"**.

#### Windsurf

Open or create `~/.codeium/windsurf/mcp_config.json` and add:

```json
{
  "mcpServers": {
    "brainpack": {
      "command": "brainpack",
      "args": ["mcp-server"]
    }
  }
}
```

Or go to Command Palette → **"MCP: Add Server"**.

#### Zed

In `~/.config/zed/settings.json`:

```json
{
  "context_servers": {
    "brainpack": {
      "source": "custom",
      "command": "brainpack",
      "args": ["mcp-server"]
    }
  }
}
```

#### Google Antigravity

Go to **Manage MCP Servers** → **View raw config** and add:

```json
{
  "mcpServers": {
    "brainpack": {
      "command": "brainpack",
      "args": ["mcp-server"]
    }
  }
}
```

#### Any other MCP-compatible agent

The command is `brainpack mcp-server`. It runs a stdio MCP server, compatible with any agent that supports the MCP protocol.

---

### Step 3: Ask your agent

Once connected, just talk to your agent:

```
Create a new Brainpack pack called "ai-research" and add this article: https://example.com/article. Then build the pack.
```

```
Add this YouTube video to my "ai-research" pack and rebuild it: https://youtube.com/watch?v=...
```

```
What does my "ai-research" pack say about retrieval-augmented generation?
```

Your agent calls the right MCP tools behind the scenes. You never need to touch the terminal for day-to-day use.

---

## How Packs Work

1. Brainpack fetches or loads your source content
2. It extracts text or generates transcripts (for audio/video)
3. It chunks the content into indexed segments
4. It embeds those chunks into a local vector store
5. At query time, it retrieves the best-matching results

Everything is local. No data is sent anywhere. Packs are just files on your disk.

Brainpack uses a multilingual embedding model by default, so it works well for non-English content too, not just English sources.

---

## Example Prompts

| What you want | What to say |
|---------------|-------------|
| Build a new pack | `Create a Brainpack pack called "my-pack", add this source: [URL], and build it.` |
| Add to an existing pack | `Add [URL] to my "my-pack" Brainpack pack and rebuild it.` |
| Ask a question | `Search my "my-pack" Brainpack pack for everything it says about [topic].` |
| Add a YouTube playlist | `Add this YouTube playlist to a new Brainpack pack called "podcast-notes" and build it: [URL]` |
| Check your packs | `List my Brainpack packs and show me their status.` |

---

## Supported Sources

| Type | Examples |
|------|----------|
| Web articles | Any public URL |
| YouTube | Videos and playlists |
| Podcasts | RSS feed URLs |
| Local text | `.txt`, `.md`, `.rst`, `.html` |
| Local audio | `.mp3`, `.m4a`, `.wav` |
| Local video | `.mp4`, `.mov`, `.mkv`, `.webm` |

Local files stay in place. Brainpack reads them where they are and does not move them.

---

## MCP Tools Reference

These are the tools Brainpack exposes to your agent. Your agent uses them automatically. You do not need to call them yourself.

| Tool | What it does |
|------|-------------|
| `packs` | List all installed packs |
| `status` | Show details and readiness for a pack |
| `retrieve` | Return relevant results for a query |
| `add` | Add a pack from a path, URL, or YAML |
| `add_sources` | Append new source URLs to a pack and rebuild |
| `build` | Build or update a pack |

---

## All Commands

| Command | What it does |
|---------|-------------|
| `brainpack create` | Create a new pack interactively |
| `brainpack add <path-or-url>` | Import an existing pack from a file or URL |
| `brainpack build <pack>` | Build or rebuild a pack |
| `brainpack update <pack>` | Update a pack with new content |
| `brainpack remove <pack>` | Remove a pack |
| `brainpack list` | List all installed packs |
| `brainpack status <pack>` | Show pack details and readiness |
| `brainpack query <pack> "question"` | Ask a question directly (requires Ollama) |
| `brainpack add-source <pack> <url>` | Add a new source to an installed pack |
| `brainpack mcp-server` | Start the MCP server |
| `brainpack settings` | View and configure settings |
| `brainpack check-deps` | Verify runtime dependencies |
| `brainpack about` | Version and info |
| `brainpack help` | List all commands |

---

## Local Model (Ollama)

You can use Brainpack with a local model too, without sending anything to an external API. This lets you query your packs entirely on your own machine.

> **If you only use Brainpack through an MCP-connected agent (Claude Code, Codex, etc.), you do not need Ollama.** Your agent is the LLM. Brainpack just retrieves results for it.

**Setup:**

1. Download and install Ollama from [ollama.com](https://ollama.com)
2. Pull a model:

```bash
ollama pull llama3.2     # 2 GB, fast, good for most queries
ollama pull qwen2.5:7b   # 4.7 GB, stronger reasoning
```

3. Start Ollama in a terminal and keep it running:

```bash
ollama serve
```

4. In another terminal, build a pack and query it:

```bash
brainpack query my-pack "What does this source say about X?"
```

To change the model, run `brainpack settings`.

---

## Troubleshooting

### Pack is not queryable yet

```bash
brainpack status my-pack
brainpack build my-pack
```

A `partial` pack may still be usable. Rebuilding recovers any failed sources.

### MCP is connected but retrieval is not working

- Make sure the pack was built: `brainpack status my-pack`
- Restart your agent after adding Brainpack for the first time
- Verify the server is registered: `claude mcp list`
- Make sure the same Brainpack installation is used by both CLI and the MCP server

### YouTube or audio builds fail

- Check that `ffmpeg` is installed: `ffmpeg -version`
- Check that `yt-dlp` is installed and current: `yt-dlp --version`
- Make sure the source URL is still reachable

### Which `python` / `pip` should I use?

Use the same Python environment for installation and for the MCP server. If you installed with `pip install brainpack`, running `brainpack mcp-server` will use that same environment automatically.

---

## Development (from the repo)

```bash
git clone https://github.com/buralog/brainpack.git
cd brainpack
uv sync
```

Run commands from the repo:

```bash
uv run python -m brainpack.cli help
```

MCP config for a local repo install:

```bash
claude mcp add brainpack -- uv run python -m brainpack.cli mcp-server --cwd /absolute/path/to/brainpack
```

Or manually in your agent's config file:

```json
{
  "mcpServers": {
    "brainpack": {
      "command": "uv",
      "args": ["run", "python", "-m", "brainpack.cli", "mcp-server"],
      "cwd": "/absolute/path/to/brainpack"
    }
  }
}
```

Run tests:

```bash
uv run pytest tests/test_cli.py tests/test_mcp_server.py
```

---

## Contributing

Issues and pull requests are welcome at [github.com/buralog/brainpack](https://github.com/buralog/brainpack).

---

## Legal

This project is intended for educational and personal productivity use. Users are responsible for ensuring their use of any content (YouTube videos, blog posts, etc.) complies with applicable copyright laws and the terms of service of the respective platforms. Brainpack does not host, copy, or redistribute any content — it is a local processing bridge that operates entirely on the user's own machine.

## License

MIT
