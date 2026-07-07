# retrace

**Search everything your AI coding agents ever did — and any local folder — in one place.**

`retrace` is a local, zero-dependency web app that unifies the session history of
**Claude Code**, **Codex**, and **Cline** (plus any folders you add) into one
search-first interface, grouped by the real project you were working in.

![retrace — one search across Claude, Codex, Cline and local files](docs/retrace-demo.png)

*(demo data — search `checkout` across all providers in a sample `acme-store` project)*

- 🔒 **Local & private** — reads files under your home dir, read-only. Nothing leaves your machine.
- ⚡ **Fast** — full-text search powered by [ripgrep](https://github.com/BurntSushi/ripgrep) (with a pure-Python fallback). No index to build, always fresh.
- 🧩 **Unified by project** — the same repo's history from different tools shows under one entry.
- 📁 **Beyond AI history** — add any local folder as a source and full-text search it too.
- 🪶 **Zero dependencies** — Python 3 standard library only. One command to run.

> **Not comfortable with the terminal?** See the plain-English
> [Getting Started guide](docs/GETTING-STARTED.md) — download the ZIP and double-click
> `start-retrace.command` (Mac) or `start-retrace.bat` (Windows).

## Quickstart

```bash
git clone <your-repo-url> retrace && cd retrace
python3 server.py            # auto-picks a free port
# open the printed http://127.0.0.1:<port>
```

Or use the launcher (start / stop / restart):

```bash
./start.sh            # start on :8787
./start.sh stop
./start.sh restart
```

> **Tip (VS Code):** open the URL in the built-in Simple Browser
> (`⌘⇧P` → *Simple Browser: Show*) to keep it embedded in your editor.

### Try it with sample data (no real history needed)

```bash
python3 demo/seed_demo.py          # writes a fictional dataset to demo/data/
RETRACE_CLAUDE_DIR=demo/data/claude \
RETRACE_CODEX_DIR=demo/data/codex \
RETRACE_CLINE_DIR=demo/data/cline/data \
    python3 server.py --port 8788 --no-open
# then add demo/data/notes as a folder source in the UI and search "checkout"
```

The `RETRACE_*_DIR` env vars override where each provider is read from (handy for
testing, demos, or non-standard install locations).

## What it reads

| Source | Location | Notes |
|--------|----------|-------|
| Claude Code | `~/.claude/projects/**/*.jsonl` + `memory/` | transcripts + memory |
| Codex | `~/.codex/sessions/**/*.jsonl` | titles from `session_index.jsonl` |
| Cline | `~/.cline/data` | metadata in SQLite, transcripts in JSON |
| Custom folders | anything you add in the UI | full-text + filename search |

Missing tools are simply skipped — run it with whatever you have installed.

## Features

- **Search-first UI** — one box + filter chips: provider, source (history/memory), whole-word.
- **Whole-word** matching (toggle off for substring); multiple keywords are AND-matched.
- **Grouped by session/file**, ranked by relevance.
- Click a result → full **transcript** (AI) or **file preview** (folders), with matches highlighted.
- **Per-result actions** on every hit — **Open** (default app), **Copy path** (grab the absolute path to paste elsewhere / hand to another agent), and **Reveal ↗** (Finder / Explorer). Works for AI transcripts (`.jsonl`), memory (`.md`), and folder-source files; retrace never edits them.
- **Add/remove folder sources** from the UI. Content is searched for text files; **all files are findable by name** (so `.docx`/`.xlsx`/`.pdf` show up by filename).
- **Sort & group** results (by relevance/date/space/provider; group headers collapse).

> **New here?** Every filter chip and control is explained in the
> [Search filters & controls guide](docs/search-filters.md).

## Custom folder sources

Click **+** next to *Sources* in the sidebar and enter a folder path. Sources persist in
`sources.json` (git-ignored). Scans respect `.gitignore` and skip binaries.

**Note:** raw content search only works for text files (`.md`, `.txt`, `.csv`, `.json`, code, …).
Binary formats (`.docx`, `.xlsx`, `.pptx`, `.pdf`) are matched **by filename** only.

## Security

- The file-preview endpoint (`/api/file`) is **sandboxed**: it only serves files inside a
  configured source root (symlinks resolved, path traversal blocked).
- The server binds to `127.0.0.1` — local only.

## Requirements

- **Python 3.9+** — the only hard requirement.
- **[ripgrep](https://github.com/BurntSushi/ripgrep) (strongly recommended)** — retrace uses it as
  the search engine when present. It's dramatically faster on large corpora *and* more accurate
  (the pure-Python fallback can under-match). Without it, retrace still works via a built-in
  fallback scanner — you'll see `· python fallback` in the results header.

  ```bash
  # macOS
  brew install ripgrep
  # Debian/Ubuntu
  sudo apt install ripgrep
  # Fedora
  sudo dnf install ripgrep
  # Arch
  sudo pacman -S ripgrep
  # Windows
  winget install BurntSushi.ripgrep.MSVC   # or: choco install ripgrep / scoop install ripgrep
  # any platform with Rust
  cargo install ripgrep
  ```

  After installing, restart retrace (`./start.sh restart`). retrace auto-detects `rg` on `PATH` —
  no config needed.

  > ripgrep is open source (MIT / Unlicense), by Andrew Gallant, and ships inside VS Code and many
  > distros — a well-audited dependency. Homebrew and the release binaries are checksum-verified;
  > use `brew install --build-from-source ripgrep` or `cargo install ripgrep` if you prefer to
  > compile locally.

## How it works

A tiny stdlib `http.server` serves a single static page and a small JSON API. Each provider is an
**adapter** (`parser.py`, `codex.py`, `cline.py`, `sources.py`) that maps a tool's on-disk format
to a shared model; `search.py` orchestrates ripgrep across them and groups results by real project.
Adding a new tool = one adapter module.

## License

MIT — see [LICENSE](LICENSE).
