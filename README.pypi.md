<div align="center">

#  beyin
### base engine for your information nodes

*also means “brain” in Turkish.*

**Build local, queryable packs from videos, articles, podcasts, and local files. <br>
Query them through MCP with your AI agent, or explore them directly with a local model.**

[![PyPI](https://img.shields.io/pypi/v/beyin?style=flat-square&color=3775A9)](https://pypi.org/project/beyin/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-2E8B57?style=flat-square)](https://modelcontextprotocol.io)
[![Ollama](https://img.shields.io/badge/Ollama-supported-2E8B57?style=flat-square)](https://ollama.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-2E8B57?style=flat-square)](LICENSE)

</div>

## ✨ Features

- 🔗 **MCP compatible:** works with Claude Code, Codex, Cursor, Windsurf, Zed and more
- 🔄 **Cross-agent packs:** build once, then use the same local packs from any MCP-compatible agent or the CLI
- 📦 **Local-first pipeline:** processing, embedding, and storage all happen on your machine
- 🎬 **Rich source support:** YouTube videos and playlists, podcasts, PDFs, articles, local files
- 🌍 **50+ languages:** multilingual embedding model out of the box
- 🤖 **Ollama support:** run fully offline with a local model
- ⚡ **Plug and play:** one command to connect via MCP, then manage everything by just talking to your agent
- 🎯 **Multi-query expansion:** generates query variants automatically for better retrieval

## ⚙️ How it works

The recommended way to use beyin is through MCP with the AI agent you already use.

Your packs are local to your machine, not tied to one agent session or vendor. Connect beyin to Codex, Claude Code, Cursor, or another MCP client and access the same packs from whichever one you want.

1. Install beyin and connect it to your agent once
2. Tell your agent to create a pack, add your sources, and build it
3. Ask questions naturally and let your agent handle retrieval

It becomes part of your agent’s natural workflow, bringing in the right context exactly when you need it while keeping you focused.

See [Example Usage with MCP](#-example-usage-with-mcp) for real prompts and workflows.

You can also query packs directly with a local model, no external API or agent needed. See [Query with a Local Model](#-query-with-a-local-model).

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

> beyin is built for local processing on your own machine. Use it with content you are allowed to process, preferably public, permitted sources or material you own or have rights to use. Avoid copied, paywalled, private, restricted, or illegally shared content.

## 📦 Installation

We recommend `uv` because it keeps the CLI install isolated and gives you a plain `beyin` command on your `PATH`.

If you do not have `uv` yet, install it first:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Package manager alternatives also work, for example `brew install uv` on macOS or `winget install --id=astral-sh.uv -e` on Windows. See the official `uv` installation guide for more options: [docs.astral.sh/uv/getting-started/installation](https://docs.astral.sh/uv/getting-started/installation/).

The recommended way to install beyin is with `uv`:

```bash
uv tool install beyin
```

If you later want optional document support such as `.pdf`, `.docx`, or `.xlsx`, install those Python packages in the same environment as beyin. For `uv tool install` users, rerun the install with all desired extras in one command, for example:

```bash
uv tool install --reinstall --with pdfplumber --with openpyxl beyin
```

If you already manage a dedicated Python environment and explicitly want beyin inside it, `pip install beyin` still works, but it is a fallback path rather than the recommended default.

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

### Windows note

If you are on Windows and plan to use beyin through Codex MCP, prefer WSL over native Windows. See [Windows notes](#windows-notes) for the recommended setup and details.

## 🖥️ Using via CLI

You can use beyin directly in your terminal without MCP:

```bash
beyin
```

If you want to verify runtime dependencies before building anything:

```bash
beyin check-deps
```

If this is a fresh install, your first text build may ask for the NLTK `punkt_tab` tokenizer data. That is expected. Install it into the current beyin environment with:

```bash
beyin check-deps --fix
```

After that, rerun your `beyin build ...` command.

What happens on first run:

- beyin starts a guided setup flow
- after setup, if you do not have any packs yet, beyin shows a start screen where you can create a new pack or import an existing one
- if setup is already complete and no packs are available, that same start screen is shown again
- if you already have packs, you can manage and build them from the CLI as usual

Useful examples:

```bash
beyin
beyin help
beyin list
beyin build my-pack
beyin settings
beyin check-deps
```

If you do not want a persistent install, you can run the same commands with `uvx beyin ...` instead.

## 🔌 Connect to Your Agent

You only need to do this once.

`beyin` runs as a stdio MCP server. After registration, your MCP client launches and manages the server for you, so you do not need to keep a separate terminal open. If the tool does not appear immediately, restart the client.

Permission note: MCP clients often ask for approvals on first use while the agent explores the repo, reads local files, checks your environment, or installs missing tools. That is normal. There is no single cross-client MCP permission command for this; approval controls are client-specific. If you trust the current workspace and want a smoother setup, prefer your client's broader allow/auto-run option for recurring local actions instead of approving each small step one by one.

#### Claude Code

```bash
claude mcp add beyin -- beyin mcp-server
```

To make it available across all your projects:

```bash
claude mcp add --scope user beyin -- beyin mcp-server
```

#### Codex

```bash
codex mcp add beyin -- beyin mcp-server
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

#### Any other MCP-compatible agent

Recommended command:

```bash
beyin mcp-server
```

Use this as the MCP server command in any client that supports the MCP protocol. Your client will launch and manage it for you, so you do not need to run it manually in a separate terminal.

## 💬 Example Usage with MCP

Once beyin is connected through MCP, you can talk to your agent naturally. You do not need to memorize commands or even say "beyin" every time. Just ask for what you want.

You also do not need to stay inside one agent forever. The packs live locally, so after setup you can switch between MCP clients and keep using the same packs.

> Some prompts that mention local files or folders may require your AI agent to have read access to those locations first.

| What you want | What to say |
|---------------|-------------|
| Build a new pack | `create a pack called yt-research, add this YouTube playlist: https://youtube.com/playlist?list=..., and build it` |
| Add a source | `I have a PDF about growth strategy in my Downloads folder, add it to my mobile-marketing pack and rebuild` |
| Add more sources | `add these to my product ideas pack and rebuild: https://example.com/article-1, https://example.com/article-2, https://example.com/article-3` |
| Ask a question | `any useful info about onboarding screens in my mobile marketing pack?` |
| Control the response | `ask yt-research pack about building an audience from scratch, include sources and timestamps` |
| Check your packs | `list my packs and show me their status` |
| Ask about a pack | `whats the status of mobile marketing pack? and what about its sources?` |
| Check runtime support | `what dependencies are available for beyin on this machine? do we support pdf, xlsx, youtube, and local query right now?` |
| Remove a source | `remove sources 2 and 3 from mobile marketing pack` |
| Remove a pack | `remove that pack about tech podcast` |

## 🛠️ MCP Tools Reference

These are the tools beyin exposes to your agent. Your agent uses them automatically; you do not need to call them yourself.

| Tool | What it does |
|------|-------------|
| `packs` | List all installed packs |
| `status` | Show details and readiness for a pack |
| `dependencies` | Inspect runtime dependencies and optional document-source support for the current beyin install |
| `retrieve` | Return relevant results for one or more queries |
| `build` | Build or update a pack. Pass `sources` to build only selected sources by index or range. Automatically purges chunks of removed sources. |
| `add` | Add a pack from a path, URL, or YAML (`in progress`) |
| `add_sources` | Add new sources to a pack. Rebuilds automatically for single sources; playlists/feeds are expanded for review first. |
| `remove_sources` | Remove sources by index, range, or text match. Removed chunks stay in the vector store until you rebuild. |
| `remove` | Remove an installed pack (moves to trash) |
| `registry` | Browse the beyin community registry by topic, tag, or keyword (`in progress`) |

## 📋 All Commands

**Pack lifecycle**

| Command | What it does |
|---------|-------------|
| `beyin create` | Create a new pack interactively |
| `beyin add <path-or-url>` | Import an existing pack from a file or URL |
| `beyin build <pack>` | Build or rebuild a pack |
| `beyin update <pack>` | Fetch new content and rebuild incrementally |
| `beyin remove <pack>` | Remove a pack |
| `beyin list` | List all installed packs |
| `beyin status <pack>` | Show pack details and readiness |

**Sources**

| Command | What it does |
|---------|-------------|
| `beyin add-source <pack> <url>` | Add a new source to an installed pack |
| `beyin remove-source <pack> <selector>` | Remove a source by index, range, or text match |

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

### Common Examples

#### Build

| Command | What it does |
|---------|-------------|
| `beyin build <pack>` | Build all current pack sources |
| `beyin build <pack> --source 2` | Build one selected source by index |
| `beyin build <pack> --source 1-3` | Build a selected source range |
| `beyin build <pack> --source "keyword"` | Build selected sources by visible text match |
| `beyin build <pack> --model tiny --language tr` | Override Whisper model and language for this build |
| `beyin build <pack> --reset` | Clear runtime artifacts and rebuild from scratch |

#### Add Sources

| Command | What it does |
|---------|-------------|
| `beyin add-source <pack> <url>` | Add one source |
| `beyin add-source <pack> <url-1> <url-2>` | Add multiple sources in one command |
| `beyin add-source <pack> ./notes.md` | Add a supported local file path as a source |
| `beyin add-source <pack> <url> --build` | Add source(s) and build immediately |

If a URL contains shell-sensitive characters such as `?` or `&`, quote it first. This is especially important in shells like `fish`.

```bash
beyin add-source my-pack "https://www.youtube.com/watch?v=vd14EElCRvs"
```

#### Remove Sources

| Command | What it does |
|---------|-------------|
| `beyin remove-source <pack> 2` | Remove source by index |
| `beyin remove-source <pack> 1 3 5` | Remove multiple sources by index |
| `beyin remove-source <pack> 1-3` | Remove a range of sources |
| `beyin remove-source <pack> "keyword"` | Remove a source by title or URL text match |
| `beyin remove-source <pack> 2 --build` | Remove and rebuild immediately to clean up vector store |

## 🤖 Query with a Local Model

You can query your packs with a local model using Ollama, without sending anything to an external API. Everything stays on your machine.

> **If you use beyin through an MCP-connected agent (Claude Code, Codex, etc.), you do not need Ollama.** Your agent is the LLM. beyin just retrieves results for it.

**Setup:**

1. Download and install Ollama from [ollama.com](https://ollama.com)
2. Pull a model:

```bash
# Example models
ollama pull llama3.2     # 2 GB, fast, good for most queries
ollama pull qwen2.5:7b   # 4.7 GB, stronger reasoning
```

3. Check that Ollama is reachable and that your model is installed:

```bash
ollama list
```

`ollama list` shows the models installed in your local Ollama instance. It is also a quick connectivity check: if it returns a normal table, beyin can usually reach the Ollama daemon too.

Important distinction:

- `ollama pull ...` downloads a model into your local Ollama instance
- `ollama list` shows the models currently installed locally
- `ollama serve` starts the local Ollama API server if it is not already running

Platform note:

- On Linux, Ollama is often already running as a background service after installation, so `ollama list` may work immediately and you may not need to run `ollama serve` yourself.
- On macOS, depending on how Ollama was started, you may need to launch the Ollama app or run `ollama serve` manually before local queries work.

If `ollama list` fails, start Ollama and try again:

```bash
ollama serve
```

4. Query with beyin:

```bash
beyin query my-pack "What does this source say about X?"
```

If beyin says a model was not found, compare the exact model tag in `beyin settings` with the output of `ollama list`.

To change the model, run `beyin settings`.

## 🔧 Troubleshooting

- [Pack is not queryable yet](#pack-is-not-queryable-yet)
- [MCP is connected but retrieval is not working](#mcp-is-connected-but-retrieval-is-not-working)
- [Audio and video builds are slow](#audio-and-video-builds-are-slow)
- [Video or audio builds fail](#video-or-audio-builds-fail)
- [Pack name with spaces is not recognized](#pack-name-with-spaces-is-not-recognized)
- [Which install path should I use?](#which-install-path-should-i-use)
- [Windows notes](#windows-notes)

### Pack is not queryable yet

```bash
beyin status my-pack
beyin build my-pack
```

A `partially-ready` pack is still queryable — sources that built successfully are available. Rebuilding recovers any failed sources.

### MCP is connected but retrieval is not working

- Make sure the pack was built: `beyin status my-pack`
- Restart your agent after adding beyin for the first time
- Verify that beyin is registered in your MCP client
- Make sure the same beyin installation is used by both CLI and the MCP server

### Audio and video builds are slow

beyin uses Whisper to transcribe audio and video sources. Model size controls the trade-off between speed, memory use, and transcription quality. English-only `.en` variants through `medium.en` are useful when you know the audio is only English.

| Model | Type | Parameters | Download size | Speed | Accuracy | Best for |
|-------|------|------------|---------------|-------|----------|----------|
| `tiny` | multilingual | 39M | ~75 MB | fastest | lowest | Quick tests, clean audio, mixed-language detection |
| `tiny.en` | English-only | 39M | ~75 MB | fastest | low | Fastest English-only transcripts |
| `base` | multilingual | 74M | ~145 MB | fast | low | Simple podcasts, lightweight multilingual audio |
| `base.en` | English-only | 74M | ~145 MB | fast | low+ | English podcasts and interviews |
| `small` | multilingual | 244M | ~483 MB | moderate | good | Most use cases, multilingual content |
| `small.en` | English-only | 244M | ~483 MB | moderate | good+ | Strong default for English-only speech |
| `medium` | multilingual | 769M | ~1.5 GB | slow | better | Harder English, multilingual, accented, or noisy audio |
| `medium.en` | English-only | 769M | ~1.5 GB | slow | better+ | Higher English accuracy without multilingual support |
| `large` | multilingual | 1.55B | ~3 GB | slowest | best | Maximum accuracy, difficult audio |

The default model is `small`. To use a faster or English-only model, change it in settings:

```bash
beyin settings
```

Or pass it per build:

```bash
beyin build my-pack --model small
```

`small` is a good default for most content. If your audio is strictly English, `small.en` is a good faster/simpler option. Use `medium`, `medium.en`, or `large` for harder audio.

### Video or audio builds fail

- Check that `ffmpeg` is installed: `ffmpeg -version`
- Check that `yt-dlp` is installed and current: `yt-dlp --version`
- Make sure the source URL is still reachable

### Pack name with spaces is not recognized

Pack IDs use kebab-case, not spaces. Use `my-pack` instead of `my pack`. The display name can be anything, but the ID used in commands must be kebab-case.

### Which install path should I use?

Prefer one of these two patterns and stay consistent:

- Installed workflow: `uv tool install beyin`, then run `beyin ...`
- No-install workflow: run `uvx beyin ...`

Why `uv` is the main path:

- `uv tool install` installs beyin as a standalone CLI app instead of dropping it into whatever Python environment happens to be active
- you get a plain `beyin` command on your `PATH`, so day-to-day usage stays simple
- the install is isolated, which avoids environment drift and version clashes from unrelated Python projects
- it is easier to keep CLI usage and agent/MCP usage aligned when beyin is installed as one managed tool

Do not mix them casually across CLI and MCP setup, or you may end up checking one environment and running another. `pip install beyin` is available if you explicitly want beyin inside a managed Python environment, but it is not the main path.

### Windows notes

The main `beyin ...` commands stay the same on Windows after installation. The examples above use Unix-like shell syntax and config paths in a few places, so if a path does not match your system, use the equivalent settings location for your MCP client on Windows. For media builds, install `ffmpeg` first, then rerun `beyin check-deps`.

If you are using Codex through MCP on Windows, prefer WSL over native Windows. In testing, native Windows CLI installs could work, but Codex MCP calls were noticeably less reliable there, with long cold starts or repeated stuck first calls when using both `beyin mcp-server` and `uvx beyin mcp-server`. WSL was much more consistent.

Recommended Windows setup for Codex:

1. Install WSL and open your Linux distro terminal.
2. Install `uv` inside WSL.
3. Install beyin inside WSL with `uv tool install beyin`.
4. Add the MCP server from the same WSL environment with `codex mcp add beyin -- beyin mcp-server`.

## 🧑‍💻 Development

```bash
git clone https://github.com/buralog/beyin.git
cd beyin
uv sync
```

Run commands from the repo:

```bash
uv run beyin help
```

MCP config for a local repo install:

```bash
claude mcp add beyin -- uv run beyin mcp-server --cwd /absolute/path/to/beyin
```

Or manually in your agent's config file:

```json
{
  "mcpServers": {
    "beyin": {
      "command": "uv",
      "args": ["run", "beyin", "mcp-server"],
      "cwd": "/absolute/path/to/beyin"
    }
  }
}
```

Run tests:

```bash
uv run pytest tests/test_cli.py tests/test_mcp_server.py
```

## 🔍 Behind the Scenes

1. beyin fetches or loads your source content
2. It extracts text or generates transcripts (for audio/video)
3. It chunks the content into indexed segments
4. It embeds those chunks into a local vector store
5. At query time, it retrieves the best-matching chunks using multi-query expansion

beyin uses a multilingual embedding model by default, so it works well across 50+ languages.

> **Privacy note:** Steps 1–4 are entirely local. At step 5, only the retrieved chunks reach your LLM. For full privacy, use beyin with Ollama so nothing leaves your machine.

## 🤝 Contributing

Issues and pull requests are welcome at [github.com/buralog/beyin](https://github.com/buralog/beyin).

See [CONTRIBUTING.md](CONTRIBUTING.md) for pack submissions, pack policy, and code contribution guidelines.

## ⚖️ Legal

beyin does not host, publish, or redistribute third-party content. Any retrieval, transcription, indexing, or embedding of source material happens locally on the end user's own machine.

Users are responsible for ensuring that their use of beyin complies with applicable laws, copyright rules, and the terms of service of the source platforms.

## 📄 License

MIT
