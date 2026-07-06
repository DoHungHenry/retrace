"""Codex CLI history adapter — ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl.

Codex schema differs from Claude: each record is {timestamp, type, payload}. Human
turns are `response_item` with payload {type:"message", role, content:[{text}]}; the
first line is `session_meta` carrying cwd/id/timestamp. Titles come from the tiny
~/.codex/session_index.jsonl (id → thread_name). No memory concept.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

# Override for tests/demo: RETRACE_CODEX_DIR points at the .codex root
_CODEX_ROOT = Path(os.environ.get("RETRACE_CODEX_DIR", "~/.codex")).expanduser()
SESSIONS_ROOT = _CODEX_ROOT / "sessions"
INDEX_FILE = _CODEX_ROOT / "session_index.jsonl"

_meta_cache: dict[str, tuple[float, dict]] = {}   # path -> (mtime, {cwd,ts,id})
_index_cache: tuple[float, dict] | None = None    # (mtime, {id: title})
_projects_cache: tuple[tuple, list] | None = None
_id_path_cache: dict[str, Path] = {}


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


def _read_index() -> dict:
    global _index_cache
    mt = _mtime(INDEX_FILE)
    if _index_cache and _index_cache[0] == mt:
        return _index_cache[1]
    idx: dict = {}
    try:
        with INDEX_FILE.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                    idx[o.get("id")] = o.get("thread_name", "")
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    _index_cache = (mt, idx)
    return idx


def _id_from_name(name: str) -> str:
    stem = name[:-6] if name.endswith(".jsonl") else name
    parts = stem.split("-")
    return "-".join(parts[-5:]) if len(parts) >= 5 else stem  # trailing uuid


def session_meta(path: Path) -> dict:
    """First-line session_meta → {cwd, ts, id}, cached by mtime."""
    key = str(path)
    mt = _mtime(path)
    hit = _meta_cache.get(key)
    if hit and hit[0] == mt:
        return hit[1]
    meta = {"cwd": "", "ts": "", "id": _id_from_name(path.name)}
    try:
        with path.open(encoding="utf-8") as fh:
            first = fh.readline()
        o = json.loads(first)
        if o.get("type") == "session_meta":
            p = o.get("payload", {})
            meta["cwd"] = p.get("cwd", "") or ""
            meta["ts"] = p.get("timestamp", "") or o.get("timestamp", "")
            meta["id"] = p.get("id", meta["id"])
    except (OSError, json.JSONDecodeError):
        pass
    _meta_cache[key] = (mt, meta)
    return meta


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") in ("input_text", "output_text", "text")
        )
    return ""


def list_projects() -> list[dict]:
    """One entry per distinct cwd (Codex's notion of a 'project')."""
    global _projects_cache
    files = list(SESSIONS_ROOT.rglob("rollout-*.jsonl"))
    sig = (len(files), max((_mtime(f) for f in files), default=0.0))
    if _projects_cache and _projects_cache[0] == sig:
        return _projects_cache[1]
    groups: dict[str, dict] = {}
    for f in files:
        m = session_meta(f)
        cwd = m["cwd"] or "(unknown)"
        g = groups.setdefault(cwd, {"count": 0, "last": ""})
        g["count"] += 1
        if m["ts"] > g["last"]:
            g["last"] = m["ts"]
    out = [{
        "provider": "codex", "dir": cwd, "realPath": cwd,
        "sessionCount": g["count"], "lastActivity": _epoch(g["last"]),
        "hasMemory": False,
    } for cwd, g in groups.items()]
    out.sort(key=lambda p: p["lastActivity"], reverse=True)
    _projects_cache = (sig, out)
    return out


def session_list(cwd: str) -> list[dict]:
    idx = _read_index()
    out = []
    for f in SESSIONS_ROOT.rglob("rollout-*.jsonl"):
        m = session_meta(f)
        if (m["cwd"] or "(unknown)") != cwd:
            continue
        out.append({
            "id": m["id"], "title": idx.get(m["id"], "") or "", "lastPrompt": "",
            "start": m["ts"], "end": m["ts"], "msgCount": 0, "model": "",
            "outputTokens": 0, "gitBranch": "",
        })
    out.sort(key=lambda s: s["end"] or "", reverse=True)
    return out


def _path_for_id(sid: str) -> Path | None:
    hit = _id_path_cache.get(sid)
    if hit and hit.is_file():
        return hit
    for f in SESSIONS_ROOT.rglob(f"*{sid}.jsonl"):
        _id_path_cache[sid] = f
        return f
    return None


def transcript(cwd: str, session_id: str, cap: int = 4000) -> list[dict]:
    path = _path_for_id(session_id)
    if not path:
        return []
    msgs = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") != "response_item":
                    continue
                p = rec.get("payload", {})
                if p.get("type") != "message" or p.get("role") not in ("user", "assistant"):
                    continue
                text = _content_text(p.get("content"))
                if not text:
                    continue
                if len(text) > cap:
                    text = text[:cap] + f"\n… [+{len(text) - cap} chars]"
                msgs.append({"role": p["role"], "ts": rec.get("timestamp", ""),
                             "text": text, "toolCalls": [], "toolResults": []})
    except OSError:
        return []
    return msgs


def title_for(path: Path) -> str:
    m = session_meta(path)
    return _read_index().get(m["id"], "") or m["id"][:8]


def parse_match(path_str: str, line: str, query: str, whole_word: bool,
                find_pos, snippet_at) -> dict | None:
    """Turn a matched Codex JSONL line into a normalized search result."""
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return None
    if rec.get("type") != "response_item":
        return None
    p = rec.get("payload", {})
    if p.get("type") != "message" or p.get("role") not in ("user", "assistant"):
        return None
    text = _content_text(p.get("content"))
    pos = find_pos(text, query, whole_word)
    if pos < 0:
        return None
    m = session_meta(Path(path_str))
    cwd = m["cwd"] or "(unknown)"
    return {
        "provider": "codex", "project": cwd, "locator": cwd, "source": "history",
        "role": p["role"], "ts": rec.get("timestamp", ""), "sessionId": m["id"],
        "file": Path(path_str).name, "snippet": snippet_at(text, pos, len(query)),
    }
