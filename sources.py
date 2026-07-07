"""User-defined generic file sources.

Lets the tool search arbitrary local folders (workspace artifacts, notes, repos) —
not just AI history. Config persists in sources.json next to the server. These sources
have NO parser: they're full-text searched as raw files (ripgrep), results are file+line.

Security: read_file() only serves paths *inside* a configured source root (symlinks
resolved, traversal blocked) so the file-preview endpoint can't leak arbitrary files.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from pathlib import Path

CONFIG = Path(__file__).parent / "sources.json"
_lock = threading.Lock()


def load_sources() -> list[dict]:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8")).get("sources", [])
    except (OSError, json.JSONDecodeError):
        return []


def _save(sources: list[dict]) -> None:
    CONFIG.write_text(json.dumps({"sources": sources}, indent=2), encoding="utf-8")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "src"


def add_source(label: str, path: str, glob: str = "") -> dict:
    p = Path(path).expanduser()
    if not p.is_dir():
        return {"error": f"not a directory: {path}"}
    rp = str(p.resolve())
    with _lock:
        sources = load_sources()
        if any(s["path"] == rp for s in sources):
            return {"error": "already added"}
        ids = {s["id"] for s in sources}
        base = _slug(label or p.name)
        sid, i = base, 2
        while sid in ids:
            sid, i = f"{base}-{i}", i + 1
        src = {"id": sid, "label": label or p.name, "path": rp, "glob": glob or ""}
        sources.append(src)
        _save(sources)
    return src


def remove_source(sid: str) -> dict:
    with _lock:
        _save([s for s in load_sources() if s["id"] != sid])
    return {"ok": True}


def list_sources() -> list[dict]:
    return load_sources()


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def read_file(path: str, cap: int = 200_000) -> dict | None:
    """Return {path, text, truncated} only if `path` lives under a configured source."""
    try:
        rp = Path(path).resolve()
    except OSError:
        return None
    roots = []
    for s in load_sources():
        try:
            roots.append(Path(s["path"]).resolve())
        except OSError:
            continue
    if not any(_is_within(rp, root) for root in roots):
        return None  # outside every allowed root → deny
    if not rp.is_file():
        return None
    try:
        data = rp.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return {"path": str(rp), "text": data[:cap], "truncated": len(data) > cap}


def reveal(path: str) -> dict:
    """Reveal a file in the OS file manager (Finder/Explorer). Read-only: just opens the
    OS file manager at the file, never reads or serves content — so it's unrestricted and
    can reveal any result (AI history .jsonl, memory .md, or a folder source). Uses
    subprocess arg-lists (no shell) so paths can't inject."""
    try:
        rp = Path(path).resolve()
    except OSError:
        return {"error": "bad path"}
    if not rp.exists():
        return {"error": "not found"}
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(rp)], check=False)          # Finder, selects file
        elif sys.platform.startswith("win"):
            subprocess.run(["explorer", f"/select,{rp}"], check=False)    # Explorer, selects file
        else:
            subprocess.run(["xdg-open", str(rp.parent)], check=False)     # Linux: open folder
        return {"ok": True}
    except OSError as e:
        return {"error": str(e)}


def open_path(path: str) -> dict:
    """Open a file with the OS default app (double-click equivalent). Read-only launch:
    hands the path to the OS opener, never reads content. Unrestricted like reveal()."""
    try:
        rp = Path(path).resolve()
    except OSError:
        return {"error": "bad path"}
    if not rp.exists():
        return {"error": "not found"}
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(rp)], check=False)                # macOS default app
        elif sys.platform.startswith("win"):
            subprocess.run(["cmd", "/c", "start", "", str(rp)], check=False)  # Windows default app
        else:
            subprocess.run(["xdg-open", str(rp)], check=False)           # Linux default app
        return {"ok": True}
    except OSError as e:
        return {"error": str(e)}
