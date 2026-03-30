<div align="center">

#  beyin
### base engine for your information nodes

*also means “brain” in Turkish.*

**Build local, queryable packs from videos, articles, podcasts, and local files. Query them through MCP with your AI agent, or explore them directly with a local model.**

[![PyPI](https://img.shields.io/pypi/v/beyin?style=for-the-badge)](https://pypi.org/project/beyin/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-6f42c1?style=for-the-badge)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)

</div>

<!-- add demo video here  -->

## ✨ Features

- 🔗 **MCP compatible:** works with Claude Code, Codex, Cursor, Windsurf, Zed and more
- 📦 **Local-first pipeline:** processing, embedding, and storage all happen on your machine
- 🎬 **Rich source support:** YouTube videos and playlists, podcasts, PDFs, articles, local files
- 🌍 **50+ languages:** multilingual embedding model out of the box
- 🤖 **Ollama support:** run fully offline with a local model
- ⚡ **Plug and play:** one command to connect via MCP, then manage everything by just talking to your agent
- 🎯 **Multi-query expansion:** generates query variants automatically for better retrieval

---

## ⚙️ How it works

The recommended way to use beyin is through MCP with the AI agent you already use.

1. Install beyin and connect it to your agent once
2. Build a pack from your sources
3. Ask questions naturally. Your agent handles retrieval automatically.

Once set up, you can ask your agent to create, build, and manage packs, add sources, check status, and retrieve relevant results, all in plain language. See [Example Usage with MCP](#-example-usage-with-mcp).

You can also query packs directly with a local model, no external API or agent needed. See [Query with a Local Model](#-query-with-a-local-model).

---

## 📂 Supported Sources

| Type | Examples |
|------|----------|
| Web articles | Public URLs |
| YouTube | Videos and playlists |
| Podcasts | RSS feed URLs |
| Local documents | `.pdf`, `.docx`, `.pptx`, `.epub`, `.xlsx`, `.csv` |
| Local text | `.txt`, `.md`, `.rst`, `.html` |
| Local audio | `.mp3`, `.m4a`, `.wav` |
| Local video | `.mp4`, `.mov`, `.mkv`, `.webm` |

> beyin is built for local processing on your own machine. Use it with content you are allowed to process: public sources, or material you own or have rights to use.

---

## 📦 Installation

Install with `pip` if you already manage a Python environment yourself:

```bash
pip install beyin
```

Or install it as an isolated CLI tool with `uv`:

```bash
uv tool install beyin
```

Verify your setup:

```bash
beyin check-deps
```

**ffmpeg** is required for video and audio sources. Skip if you only use articles and local files:

```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg

# Windows
winget install ffmpeg
```

No Homebrew on macOS or winget not working? Download directly from [ffmpeg.org/download.html](https://ffmpeg.org/download.html).

---

## 🔌 Connect to Your Agent

You only need to do this once.

#### Claude Code

If you installed with `pip`:

```bash
claude mcp add beyin -- beyin mcp-server
```

No config file editing needed, and **no need to keep a terminal open**. Claude Code launches and manages the server process automatically. Restart Claude Code and `beyin` will appear in your MCP tools.

To make it available across all your projects:

```bash
claude mcp add --scope user beyin -- beyin mcp-server
```

If you installed with `uv tool`, use:

```bash
claude mcp add beyin -- uvx beyin mcp-server
```

#### Codex (OpenAI)

If you installed with `pip`:

```bash
codex mcp add beyin -- beyin mcp-server
```

If you installed with `uv tool`:

```bash
codex mcp add beyin -- uvx beyin mcp-server
```

#### Cursor

Open or create `~/.cursor/mcp.json` and add:

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

Or go to Command Palette → **"View: Open MCP Settings"**.

If you installed with `uv tool`, use `"command": "uvx"` and `"args": ["beyin", "mcp-server"]` instead.

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

If you installed with `uv tool`, use `"command": "uvx"` and `"args": ["beyin", "mcp-server"]` instead.

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

If you installed with `uv tool`, use `"command": "uvx"` and `"args": ["beyin", "mcp-server"]` instead.

#### Any other MCP-compatible agent

The command is `beyin mcp-server`. It runs a stdio MCP server, compatible with any agent that supports the MCP protocol.

---

## 💬 Example Usage with MCP

Once beyin is connected through MCP, you can talk to your agent naturally. You do not need to memorize commands or even say "beyin" every time. Just ask for what you want.

> Some prompts that mention local files or folders may require your AI agent to have read access to those locations first.

| What you want | What to say |
|---------------|-------------|
| Build a new pack | `create a pack called "yt-research", add this YouTube playlist: https://youtube.com/playlist?list=..., and build it` |
| Add a source | `I have a PDF about growth strategy in my Downloads folder, add it to my "mobile-marketing" pack and rebuild` |
| Add more sources | `add these to my "product-ideas" pack and rebuild: https://example.com/article-1, https://example.com/article-2, https://example.com/article-3` |
| Ask a question | `any useful info about onboarding screens in my "mobile marketing" pack?` |
| Control the response | `ask yt-research pack about building an audience from scratch, include sources and timestamps` |
| Check your packs | `list my packs and show me their status` |
| Ask about a pack | `whats the status of mobile marketing pack? and also its sources?` |
| Remove a source | `remove sources 2 and 3 from mobile marketing pack` |
| Remove a pack | `remove that pack about tech podcast` |

---

## 🛠️ MCP Tools Reference

These are the tools beyin exposes to your agent. Your agent uses them automatically; you do not need to call them yourself.

| Tool | What it does |
|------|-------------|
| `packs` | List all installed packs |
| `status` | Show details and readiness for a pack |
| `retrieve` | Return relevant results for one or more queries |
| `build` | Build or update a pack. Pass `sources` to build only selected sources by index or range. Automatically purges chunks of removed sources. |
| `add` | Add a pack from a path, URL, or YAML |
| `add_sources` | Add new sources to a pack. Rebuilds automatically for single sources; playlists/feeds are expanded for review first. |
| `remove_sources` | Remove sources by index, range, or text match. Removed chunks stay in the vector store until you rebuild. |
| `remove` | Remove an installed pack (moves to trash) |
| `registry` | Browse the beyin community registry by topic, tag, or keyword |

---

## 📋 All Commands

**Pack lifecycle**

| Command | What it does |
|---------|-------------|
| `beyin create` | Create a new pack interactively |
| `beyin add <path-or-url>` | Import an existing pack from a file or URL |
| `beyin build <pack>` | Build or rebuild a pack |
| `beyin build <pack> --source 1 3 5` | Build only selected sources by index or range |
| `beyin update <pack>` | Fetch new content and rebuild incrementally |
| `beyin remove <pack>` | Remove a pack |
| `beyin list` | List all installed packs |
| `beyin status <pack>` | Show pack details and readiness |

**Sources**

| Command | What it does |
|---------|-------------|
| `beyin add-source <pack> <url>` | Add a new source to an installed pack |
| `beyin remove-source <pack> 2` | Remove source by index |
| `beyin remove-source <pack> 1 3 5` | Remove multiple sources by index |
| `beyin remove-source <pack> 1-3` | Remove a range of sources |
| `beyin remove-source <pack> "keyword"` | Remove a source by title/URL text match |
| `beyin remove-source <pack> 2 --build` | Remove and rebuild immediately to clean up vector store |

**Query**

| Command | What it does |
|---------|-------------|
| `beyin query <pack> "question"` | Ask a question directly (requires Ollama) |

**Server & config**

| Command | What it does |
|---------|-------------|
| `beyin mcp-server` | Start the MCP server |
| `beyin settings` | View and configure settings |
| `beyin check-deps` | Verify runtime dependencies |
| `beyin about` | Version and info |
| `beyin help` | List all commands |

---

## 🤖 Query with a Local Model

You can query your packs with a local model using Ollama, without sending anything to an external API. Everything stays on your machine.

> **If you use beyin through an MCP-connected agent (Claude Code, Codex, etc.), you do not need Ollama.** Your agent is the LLM. beyin just retrieves results for it.

**Setup:**

1. Download and install Ollama from [ollama.com](https://ollama.com)
2. Pull a model:

```bash
ollama pull llama3.2     # 2 GB, fast, good for most queries
ollama pull qwen2.5:7b   # 4.7 GB, stronger reasoning
```

3. Start Ollama:

```bash
ollama serve
```

4. Build a pack and query it:

```bash
beyin query my-pack "What does this source say about X?"
```

To change the model, run `beyin settings`.

---

## 🔧 Troubleshooting

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

### Pack name with spaces is not recognized

Pack IDs use kebab-case, not spaces. Use `my-pack` instead of `my pack`. The display name can be anything, but the ID used in commands must be kebab-case.

### Which `python` / `pip` should I use?

Use the same installation path for both CLI commands and the MCP server:

- If you installed with `pip install beyin`, use `beyin ...`
- If you installed with `uv tool install beyin`, use `uvx beyin ...`

Mixing them can make the CLI and MCP server point at different environments.

---

## 🧑‍💻 Development

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

## 🔍 Behind the Scenes

1. beyin fetches or loads your source content
2. It extracts text or generates transcripts (for audio/video)
3. It chunks the content into indexed segments
4. It embeds those chunks into a local vector store
5. At query time, it retrieves the best-matching chunks using multi-query expansion

beyin uses a multilingual embedding model by default, so it works well across 50+ languages, not just English.

> **Privacy note:** Steps 1–4 are entirely local. At step 5, only the retrieved chunks reach your LLM. For full privacy, use beyin with Ollama so nothing leaves your machine.

---

## 🤝 Contributing

Issues and pull requests are welcome at [github.com/buralog/beyin](https://github.com/buralog/beyin).

See [CONTRIBUTING.md](CONTRIBUTING.md) for pack submissions, pack policy, and code contribution guidelines.

---

## ⚖️ Legal

beyin does not host, publish, or redistribute third-party content. Any retrieval, transcription, indexing, or embedding of source material happens locally on the end user's own machine.

Users are responsible for ensuring that their use of beyin complies with applicable laws, copyright rules, and the terms of service of the source platforms.

---

## 📄 License

MIT
