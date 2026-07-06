"""Cline history adapter — ~/.cline/data.

Cline splits data: session metadata (cwd, workspace_root, prompt, timestamps,
messages_path) lives in a SQLite db (db/sessions.db); the transcript is ONE JSON
object per session at sessions/<id>/<id>.messages.json (messages[] with role +
content[].text + ts-in-ms). Project = workspace_root. No memory concept.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Override for tests/demo: RETRACE_CLINE_DIR points at the .cline/data root
DATA_DIR = Path(os.environ.get("RETRACE_CLINE_DIR", "~/.cline/data")).expanduser()
SESSIONS_DIR = DATA_DIR / "sessions"
DB = DATA_DIR / "db" / "sessions.db"

_meta_cache: tuple[float, dict] | None = None


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _epoch(iso: str) -> float:
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _iso_from_ms(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError):
        return ""


def _meta() -> dict:
    """session_id -> {cwd, workspace_root, prompt, updated_at, messages_path, model}."""
    global _meta_cache
    mt = _mtime(DB)
    if _meta_cache and _meta_cache[0] == mt:
        return _meta_cache[1]
    out: dict = {}
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)  # read-only; Cline may be live
        con.row_factory = sqlite3.Row
        for r in con.execute(
            "SELECT session_id, cwd, workspace_root, prompt, updated_at, started_at, "
            "messages_path, model FROM sessions"
        ):
            out[r["session_id"]] = {
                "cwd": r["cwd"] or "", "workspace_root": r["workspace_root"] or "",
                "prompt": r["prompt"] or "", "updated_at": r["updated_at"] or r["started_at"] or "",
                "messages_path": r["messages_path"] or "", "model": r["model"] or "",
            }
        con.close()
    except sqlite3.Error:
        pass
    _meta_cache = (mt, out)
    return out


def _project_of(meta: dict) -> str:
    return (meta.get("workspace_root") or meta.get("cwd") or "(unknown)").rstrip("/")


def list_projects() -> list[dict]:
    groups: dict[str, dict] = {}
    for m in _meta().values():
        cwd = _project_of(m)
        g = groups.setdefault(cwd, {"count": 0, "last": ""})
        g["count"] += 1
        if m["updated_at"] > g["last"]:
            g["last"] = m["updated_at"]
    return [{
        "provider": "cline", "dir": cwd, "realPath": cwd,
        "sessionCount": g["count"], "lastActivity": _epoch(g["last"]), "hasMemory": False,
    } for cwd, g in groups.items()]


def session_list(project: str) -> list[dict]:
    out = []
    for sid, m in _meta().items():
        if _project_of(m) != project.rstrip("/"):
            continue
        out.append({
            "id": sid, "title": _title(m), "lastPrompt": "", "start": m["updated_at"],
            "end": m["updated_at"], "msgCount": 0, "model": m["model"],
            "outputTokens": 0, "gitBranch": "",
        })
    out.sort(key=lambda s: s["end"] or "", reverse=True)
    return out


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") in ("text", "input_text", "output_text")
        )
    return ""


def _messages_path(session_id: str, meta: dict) -> Path:
    mp = meta.get("messages_path")
    if mp and Path(mp).is_file():
        return Path(mp)
    return SESSIONS_DIR / session_id / f"{session_id}.messages.json"


def transcript(project: str, session_id: str, cap: int = 4000) -> list[dict]:
    meta = _meta().get(session_id, {})
    path = _messages_path(session_id, meta)
    try:
        o = json.load(path.open(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    msgs = []
    for msg in o.get("messages", []):
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _content_text(msg.get("content"))
        if not text:
            continue
        if len(text) > cap:
            text = text[:cap] + f"\n… [+{len(text) - cap} chars]"
        msgs.append({"role": role, "ts": _iso_from_ms(msg.get("ts")),
                     "text": text, "toolCalls": [], "toolResults": []})
    return msgs


def _title(meta: dict) -> str:
    raw = (meta.get("prompt") or "").strip()
    # Cline wraps prompts as <user_input mode="act">…</user_input>; unwrap for a clean title
    raw = re.sub(r"</?user_input[^>]*>", "", raw).strip()
    line = raw.splitlines()[0] if raw else ""
    return line[:60]


def title_for(session_id: str) -> str:
    return _title(_meta().get(session_id, {})) or session_id[:8]


def parse_file(path_str: str, query: str, whole_word: bool, find_pos, snippet_at) -> list[dict]:
    """Cline stores a whole-JSON transcript per file, so we scan its messages directly."""
    try:
        o = json.load(open(path_str, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    sid = o.get("sessionId") or Path(path_str).parent.name
    meta = _meta().get(sid, {})
    project = _project_of(meta)
    out = []
    for msg in o.get("messages", []):
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _content_text(msg.get("content"))
        pos = find_pos(text, query, whole_word)
        if pos < 0:
            continue
        out.append({
            "provider": "cline", "project": project, "locator": sid, "source": "history",
            "role": role, "ts": _iso_from_ms(msg.get("ts")), "sessionId": sid,
            "file": Path(path_str).name, "snippet": snippet_at(text, pos, len(query)),
        })
    return out
