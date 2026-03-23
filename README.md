<div align="center">

# Brainpack

**Build local, queryable packs from text extracted from videos, articles, podcasts, and local files. Query them through MCP with your AI agent, or use a local model to explore them directly.**

[![PyPI](https://img.shields.io/pypi/v/brainpack?style=for-the-badge)](https://pypi.org/project/brainpack/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-6f42c1?style=for-the-badge)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)

</div>

---

<details>
<summary><strong>Table of Contents</strong></summary>

- [What is Brainpack?](#what-is-brainpack)
- [Use It Through Your AI Agent](#use-it-through-your-ai-agent)
- [Quick Start](#quick-start)
- [Example Usage with MCP](#example-usage-with-mcp)
- [MCP Tools Reference](#mcp-tools-reference)
- [All Commands](#all-commands)
- [Local Model (Ollama)](#local-model-ollama)
- [Troubleshooting](#troubleshooting)
- [Development (from the repo)](#development-from-the-repo)
- [Behind the Scenes](#behind-the-scenes)
- [Contributing](#contributing)
- [Legal](#legal)
- [License](#license)

</details>

---

## What is Brainpack?

Brainpack is a local-first tool for turning useful information into queryable knowledge packs.

Useful information shows up everywhere, but it rarely stays usable.

You come across valuable information worth keeping, but it remains tied to the format where you found it. A video contains insights you want to reference later. An article has details you may want to use again. A saved post, note, or file can hold something important long after you first saw it.

Brainpack was built to turn that scattered information into something structured, local, and queryable through your AI agent, so the useful parts stay accessible whenever you need them.

**How it works**
1. Build a pack from your sources
2. Connect Brainpack to your agent through MCP
3. Ask questions normally while your agent retrieves from your packs automatically

For the easiest workflow, see [Use It Through Your AI Agent](#use-it-through-your-ai-agent).

#### Supported Sources

| Type | Examples |
|------|----------|
| Web articles | Any public URL |
| YouTube | Videos and playlists |
| Podcasts | RSS feed URLs |
| Local text | `.txt`, `.md`, `.rst`, `.html` |
| Local audio | `.mp3`, `.m4a`, `.wav` |
| Local video | `.mp4`, `.mov`, `.mkv`, `.webm` |

> Brainpack is built for local processing on your own machine. Use it with content you are allowed to process, preferably public, permitted sources or material you own or have rights to use. Avoid copied, paywalled, private, restricted, or illegally shared content.

---

## Use It Through Your AI Agent

The easiest way to use Brainpack is through MCP with the AI agent you already use.

Once Brainpack is connected, you do not need to run commands or manage packs manually in the terminal. You can just talk to your agent and let it handle Brainpack through MCP behind the scenes.

You can ask your agent to:

- create, build, update and manage packs
- add new sources to a pack by providing URLs or local files
- check your local packs and their status
- check available packs in the pack hub
- retrieve relevant results in response to your questions

See [Example Usage with MCP](#example-usage-with-mcp) below for common ways to use it.

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

## Example Usage with MCP

Once Brainpack is connected through MCP, you can talk to your agent naturally. You do not need to memorize commands or even say "Brainpack" every time. Just ask for what you want, and your agent can handle the pack workflow behind the scenes.

> Some prompts that mention local files or folders, such as your Documents or Downloads folder, may require your AI agent to have read access to those locations first.

| What you want | What to say |
|---------------|-------------|
| Check your packs | `List my Brainpack packs and show me their status.` |
| Ask about a pack | `What's in my "mobile-marketing" pack? Show me the sources too.` |
| Ask a question about a pack | `Any useful info about onboarding screens in my "mobile-marketing" pack?` |
| Build a new pack | `Create a new pack called "ai-helper-tools" and add this URL I found: https://.... Then build the pack.` |
| Add a source to an existing pack | `I have a useful PDF about how to automate my app builds. It's in my Documents folder. Add it to the "ai-helper-tools" pack and rebuild it.` |
| Remove a source from a pack | `Show me the sources in "mobile-marketing", then remove source 2 from that pack.` |
| Manage the response | `Ask the "ai-helper-tools" pack what I should do about designing a new landing page. Include sources in the response and any timestamps if they exist.` |
| Remove a pack | `Remove that pack about mobile marketing stuff.` |

---

## MCP Tools Reference

These are the tools Brainpack exposes to your agent. Your agent uses them automatically. You do not need to call them yourself.

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
| `brainpack create` | Create a new pack interactively |
| `brainpack add <path-or-url>` | Import an existing pack from a file or URL |
| `brainpack build <pack>` | Build or rebuild a pack |
| `brainpack update <pack>` | Update a pack with new content |
| `brainpack remove <pack>` | Remove a pack |
| `brainpack list` | List all installed packs |
| `brainpack status <pack>` | Show pack details and readiness |
| `brainpack query <pack> "question"` | Ask a question directly (requires Ollama) |
| `brainpack add-source <pack> <source>` | Add a new source to an installed pack |
| `brainpack remove-source <pack> <selector>` | Remove a source from an installed pack by index or text match |
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

### Video or audio builds fail

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

## Behind the Scenes

1. Brainpack fetches or loads your source content
2. It extracts text or generates transcripts (for audio/video)
3. It chunks the content into indexed segments
4. It embeds those chunks into a local vector store
5. At query time, it retrieves the best-matching results

Everything is local. No data is sent anywhere. Packs are just files on your disk.

Brainpack uses a multilingual embedding model by default, so it works well for non-English content too, not just English sources.

---

## Contributing

Issues and pull requests are welcome at [github.com/buralog/brainpack](https://github.com/buralog/brainpack).

See [CONTRIBUTING.md](CONTRIBUTING.md) for pack submissions, pack policy, and code contribution guidelines.

---

## Legal

Brainpack does not host, publish, or redistribute third-party content. Public packs contain only source manifests and metadata. Any retrieval, transcription, indexing, or embedding of source material happens locally on the end user's own machine.

Users are responsible for ensuring that their use of Brainpack complies with applicable laws, copyright rules, and the terms of service of the source platforms.


## License

MIT
