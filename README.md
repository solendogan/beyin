<div align="center">

# beyin

**Build local, queryable packs from text extracted from videos, articles, podcasts, and local files. Query them through MCP with your AI agent, or use a local model to explore them directly.**

[![PyPI](https://img.shields.io/pypi/v/beyin?style=for-the-badge)](https://pypi.org/project/beyin/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-6f42c1?style=for-the-badge)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)

</div>

## What is beyin?

beyin is a local-first tool for turning useful information into queryable knowledge packs.

Useful information shows up everywhere, but it rarely stays usable.

You come across valuable information worth keeping, but it remains tied to the format where you found it. A video contains insights you want to reference later. An article has details you may want to use again. A saved post, note, or file can hold something important long after you first saw it.

beyin was built to turn that scattered information into something structured, local, and queryable through your AI agent, so the useful parts stay accessible whenever you need them.

## ✨ Features

- 🎯 Multi-query expansion — generates query variants for better retrieval
- 📦 Local-first — everything stays on your machine, nothing sent externally
- 🔗 MCP compatible — works with Claude Code, Codex, Cursor, Windsurf, Zed and more
- 🌍 50+ languages — multilingual embedding model out of the box
- 🎬 Rich source support — YouTube, podcasts, PDFs, articles, local files
- 🤖 Ollama support — use fully offline with a local model
- ⚡ No dashboard — manage everything by just talking to your agent


## **How it works**

The easiest way to use beyin is through MCP with the AI agent you already use.

1. Build a pack from your sources
2. Connect beyin to your agent through MCP
3. Ask questions naturally — your agent handles retrieval from your packs automatically

Once connected, you do not need to run commands or manage packs manually in the terminal. You can ask your agent to:

- create, build, update and manage packs
- add new sources to a pack by providing URLs or local files
- check your local packs and their status
- check available packs in the pack hub
- retrieve relevant results in response to your questions

You can also query packs directly with a local model, no external API or agent needed. See [Query with a Local Model](#query-with-a-local-model).

#### Supported Sources

| Type | Examples |
|------|----------|
| Web articles | Any public URL |
| YouTube | Videos and playlists |
| Podcasts | RSS feed URLs |
| Local text | `.txt`, `.md`, `.rst`, `.html` |
| Local documents | `.pdf`, `.docx`, `.pptx`, `.epub`, `.xlsx`, `.csv` (optional deps) |
| Local audio | `.mp3`, `.m4a`, `.wav` |
| Local video | `.mp4`, `.mov`, `.mkv`, `.webm` |

> beyin is built for local processing on your own machine. Use it with content you are allowed to process, preferably public, permitted sources or material you own or have rights to use. Avoid copied, paywalled, private, restricted, or illegally shared content.

---

## Quick Start

### Step 1: Install

```bash
pip install beyin
```

Verify your setup:

```bash
beyin check-deps
```

**Only needed for video and audio sources. Skip if you only use articles and local text:**

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
claude mcp add beyin -- beyin mcp-server
```

No config file editing needed, and **no need to keep a terminal open**. Claude Code launches and manages the server process automatically. Restart Claude Code and `beyin` will appear in your MCP tools.

To make it available across all your projects:

```bash
claude mcp add --scope user beyin -- beyin mcp-server
```

#### Codex (OpenAI)

```bash
codex mcp add beyin -- beyin mcp-server
```

#### Cursor

Open or create `~/.cursor/mcp.json` and add:

```json
{
  "beyin": {
    "command": "beyin",
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
    "beyin": {
      "command": "beyin",
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
    "beyin": {
      "source": "custom",
      "command": "beyin",
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
    "beyin": {
      "command": "beyin",
      "args": ["mcp-server"]
    }
  }
}
```

#### Any other MCP-compatible agent

The command is `beyin mcp-server`. It runs a stdio MCP server, compatible with any agent that supports the MCP protocol.

---

## Example Usage with MCP

Once beyin is connected through MCP, you can talk to your agent naturally. You do not need to memorize commands or even say "beyin" every time. Just ask for what you want, and your agent can handle the pack workflow behind the scenes.

> Some prompts that mention local files or folders, such as your Documents or Downloads folder, may require your AI agent to have read access to those locations first.

| What you want | What to say |
|---------------|-------------|
| Check your packs | `List my beyin packs and show me their status.` |
| Ask about a pack | `What's in my "mobile-marketing" pack? Show me the sources too.` |
| Ask a question about a pack | `Any useful info about onboarding screens in my "mobile-marketing" pack?` |
| Build a new pack | `Create a new pack called "ai-helper-tools" and add this URL I found: https://.... Then build the pack.` |
| Add a source to an existing pack | `I have a useful PDF about how to automate my app builds. It's in my Documents folder. Add it to the "ai-helper-tools" pack and rebuild it.` |
| Remove a source from a pack | `Show me the sources in "mobile-marketing", then remove source 2 from that pack.` |
| Manage the response | `Ask the "ai-helper-tools" pack what I should do about designing a new landing page. Include sources in the response and any timestamps if they exist.` |
| Remove a pack | `Remove that pack about mobile marketing stuff.` |

---

## MCP Tools Reference

These are the tools beyin exposes to your agent. Your agent uses them automatically. You do not need to call them yourself.

| Tool | What it does |
|------|-------------|
| `packs` | List all installed packs |
| `status` | Show details and readiness for a pack |
| `retrieve` | Return relevant results for a query |
| `add` | Add a pack from a path, URL, or YAML |
| `add_sources` | Append new sources to a pack and rebuild |
| `remove_sources` | Remove one or more sources from a pack |
| `build` | Build or update a pack |
| `remove` | Remove an installed pack |

---

## All Commands

| Command | What it does |
|---------|-------------|
| `beyin create` | Create a new pack interactively |
| `beyin add <path-or-url>` | Import an existing pack from a file or URL |
| `beyin build <pack>` | Build or rebuild a pack |
| `beyin update <pack>` | Update a pack with new content |
| `beyin remove <pack>` | Remove a pack |
| `beyin list` | List all installed packs |
| `beyin status <pack>` | Show pack details and readiness |
| `beyin query <pack> "question"` | Ask a question directly (requires Ollama) |
| `beyin add-source <pack> <source>` | Add a new source to an installed pack |
| `beyin remove-source <pack> <selector>` | Remove a source from an installed pack by index or text match |
| `beyin mcp-server` | Start the MCP server |
| `beyin settings` | View and configure settings |
| `beyin check-deps` | Verify runtime dependencies |
| `beyin about` | Version and info |
| `beyin help` | List all commands |

---

## Query with a Local Model

You can query your packs with a local model using Ollama, without sending anything to an external API. Everything stays on your machine.

> **If you use beyin through an MCP-connected agent (Claude Code, Codex, etc.), you do not need Ollama.** Your agent is the LLM. beyin just retrieves results for it.

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
beyin query my-pack "What does this source say about X?"
```

To change the model, run `beyin settings`.

---

## Troubleshooting

### Pack is not queryable yet

```bash
beyin status my-pack
beyin build my-pack
```

A `partial` pack may still be usable. Rebuilding recovers any failed sources.

### MCP is connected but retrieval is not working

- Make sure the pack was built: `beyin status my-pack`
- Restart your agent after adding beyin for the first time
- Verify the server is registered: `claude mcp list`
- Make sure the same beyin installation is used by both CLI and the MCP server

### Video or audio builds fail

- Check that `ffmpeg` is installed: `ffmpeg -version`
- Check that `yt-dlp` is installed and current: `yt-dlp --version`
- Make sure the source URL is still reachable

### Which `python` / `pip` should I use?

Use the same Python environment for installation and for the MCP server. If you installed with `pip install beyin`, running `beyin mcp-server` will use that same environment automatically.

---

## Development (from the repo)

```bash
git clone https://github.com/buralog/beyin.git
cd beyin
uv sync
```

Run commands from the repo:

```bash
uv run python -m beyin.cli help
```

MCP config for a local repo install:

```bash
claude mcp add beyin -- uv run python -m beyin.cli mcp-server --cwd /absolute/path/to/beyin
```

Or manually in your agent's config file:

```json
{
  "mcpServers": {
    "beyin": {
      "command": "uv",
      "args": ["run", "python", "-m", "beyin.cli", "mcp-server"],
      "cwd": "/absolute/path/to/beyin"
    }
  }
}
```

Run tests:

```bash
uv run pytest tests/test_cli.py tests/test_mcp_server.py
```

---

## Behind the Scenes

1. beyin fetches or loads your source content
2. It extracts text or generates transcripts (for audio/video)
3. It chunks the content into indexed segments
4. It embeds those chunks into a local vector store
5. At query time, it retrieves the best-matching results

Everything is local. No data is sent anywhere. Packs are just files on your disk.

beyin uses a multilingual embedding model by default, so it works well for non-English content too, not just English sources.

---

## Contributing

Issues and pull requests are welcome at [github.com/buralog/beyin](https://github.com/buralog/beyin).

See [CONTRIBUTING.md](CONTRIBUTING.md) for pack submissions, pack policy, and code contribution guidelines.

---

## Legal

beyin does not host, publish, or redistribute third-party content. Public packs contain only source manifests and metadata. Any retrieval, transcription, indexing, or embedding of source material happens locally on the end user's own machine.

Users are responsible for ensuring that their use of beyin complies with applicable laws, copyright rules, and the terms of service of the source platforms.


## License

MIT
