---
name: retrace-history-files
description: Start (or restart/stop) the local retrace app — search across Claude Code + Codex + Cline history and any local folder — and print its URL. Use when the user wants to open, launch, run, or browse/search their AI coding history + files.
---

# retrace launcher

Starts the local, zero-dependency web app (**retrace**) that searches AI coding history
(Claude Code, Codex, Cline) + any folders the user adds, grouped by real project.

## One-time setup

Set `RETRACE_DIR` to wherever you cloned this repo. Either export it in your shell
profile (`~/.zshrc` / `~/.bashrc`):

```bash
export RETRACE_DIR="$HOME/path/to/retrace"
```

…or replace `$RETRACE_DIR` in the commands below with your absolute clone path.
`start.sh` resolves its own location, so it works from wherever the repo lives.

## Start (default)

Starts detached on port 8787, idempotent (reports URL if already running). No external browser:

```bash
bash "$RETRACE_DIR/start.sh"
```

Then tell the user: up at **http://127.0.0.1:8787**. In VS Code, open it embedded via
⌘⇧P → "Simple Browser: Show" (bind a keybinding for one-key access).

## Other actions

- Different port: `bash "$RETRACE_DIR/start.sh" 9000`
- Stop: `bash "$RETRACE_DIR/start.sh" stop`
- Restart (after pulling/editing code): `bash "$RETRACE_DIR/start.sh" restart`

## Notes

- Requires only Python 3 (stdlib). ripgrep used if present, else a pure-Python fallback.
- Logs: `/tmp/retrace.log`. Configured folder sources persist in the repo's `sources.json` (git-ignored).
- Optional shell alias: `alias retrace='bash "$RETRACE_DIR/start.sh"'`
