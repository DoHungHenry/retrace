"""JSONL session + memory parsing for the Claude Code history viewer.

All reads are on-demand and cached by file mtime so RAM stays flat: we hold only
small per-session metadata, never full transcripts. See design report for rationale.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Override for tests/demo: RETRACE_CLAUDE_DIR
PROJECTS_DIR = Path(os.environ.get("RETRACE_CLAUDE_DIR", "~/.claude/projects")).expanduser()

# mtime-keyed caches: {path: (mtime, value)}
_session_list_cache: dict[str, tuple[float, list]] = {}
_project_path_cache: dict[str, tuple[float, str]] = {}


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def decode_dirname(dirname: str) -> str:
    """Lossy fallback: dashes -> slashes. Only used when no cwd is recorded."""
    return "/" + dirname.strip("-").replace("-", "/")


def _read_records(jsonl: Path):
    """Yield parsed JSON records from a session file, skipping malformed lines."""
    try:
        with jsonl.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def _real_path_for_project(pdir: Path) -> str:
    """Authoritative full path from a `cwd` field inside the newest session."""
    key = str(pdir)
    mt = _mtime(pdir)
    hit = _project_path_cache.get(key)
    if hit and hit[0] == mt:
        return hit[1]
    path = ""
    sessions = sorted(pdir.glob("*.jsonl"), key=_mtime, reverse=True)
    for s in sessions[:3]:  # newest few is enough to find a cwd
        for rec in _read_records(s):
            cwd = rec.get("cwd")
            if cwd:
                path = cwd
                break
        if path:
            break
    if not path:
        path = decode_dirname(pdir.name)
    _project_path_cache[key] = (mt, path)
    return path


def list_projects() -> list[dict]:
    """One entry per project dir: real path, session count, last activity, memory flag."""
    out = []
    if not PROJECTS_DIR.is_dir():
        return out
    for pdir in PROJECTS_DIR.iterdir():
        if not pdir.is_dir():
            continue
        sessions = list(pdir.glob("*.jsonl"))
        if not sessions:
            continue
        last = max((_mtime(s) for s in sessions), default=0.0)
        out.append({
            "provider": "claude",
            "dir": pdir.name,
            "realPath": _real_path_for_project(pdir),
            "sessionCount": len(sessions),
            "lastActivity": last,
            "hasMemory": (pdir / "memory").is_dir(),
        })
    out.sort(key=lambda p: p["lastActivity"], reverse=True)
    return out


def session_list(dirname: str) -> list[dict]:
    """Lightweight metadata for every session in a project (mtime-cached)."""
    pdir = PROJECTS_DIR / dirname
    if not pdir.is_dir():
        return []
    out = []
    for jsonl in pdir.glob("*.jsonl"):
        out.append(_session_meta(jsonl))
    out.sort(key=lambda s: s["end"] or "", reverse=True)
    return out


def _session_meta(jsonl: Path) -> dict:
    key = str(jsonl)
    mt = _mtime(jsonl)
    hit = _session_list_cache.get(key)
    if hit and hit[0] == mt:
        return hit[1]

    title = last_prompt = model = branch = ""
    first = last = ""
    msg_count = 0
    out_tokens = 0
    for rec in _read_records(jsonl):
        t = rec.get("type")
        if t == "ai-title":
            title = rec.get("aiTitle") or title
        elif t == "last-prompt":
            last_prompt = rec.get("lastPrompt") or last_prompt
        elif t in ("user", "assistant"):
            msg_count += 1
            ts = rec.get("timestamp")
            if ts:
                first = first or ts
                last = ts
            if t == "assistant":
                m = rec.get("message", {})
                model = m.get("model") or model
                out_tokens += (m.get("usage") or {}).get("output_tokens", 0)
            branch = rec.get("gitBranch") or branch

    meta = {
        "id": jsonl.stem,
        "title": title,
        "lastPrompt": last_prompt,
        "start": first,
        "end": last,
        "msgCount": msg_count,
        "model": model,
        "outputTokens": out_tokens,
        "gitBranch": branch,
    }
    _session_list_cache[key] = (mt, meta)
    return meta


def _block_text(content) -> tuple[str, list, list]:
    """Normalize a message.content value into (text, tool_calls, tool_results)."""
    if isinstance(content, str):
        return content, [], []
    text_parts, tool_calls, tool_results = [], [], []
    if isinstance(content, list):
        for b in content:
            if not isinstance(b, dict):
                continue
            bt = b.get("type")
            if bt == "text":
                text_parts.append(b.get("text", ""))
            elif bt == "tool_use":
                tool_calls.append({"name": b.get("name", ""), "input": b.get("input", {})})
            elif bt == "tool_result":
                c = b.get("content")
                if isinstance(c, list):
                    c = "".join(
                        x.get("text", "") for x in c if isinstance(x, dict)
                    )
                tool_results.append(str(c) if c is not None else "")
    return "\n".join(text_parts), tool_calls, tool_results


def transcript(dirname: str, session_id: str, cap: int = 4000) -> list[dict]:
    """Normalized message list for one session. Text/tool payloads capped for RAM."""
    jsonl = PROJECTS_DIR / dirname / f"{session_id}.jsonl"
    if not jsonl.is_file():
        return []
    msgs = []
    for rec in _read_records(jsonl):
        t = rec.get("type")
        if t not in ("user", "assistant"):
            continue
        text, calls, results = _block_text(rec.get("message", {}).get("content"))
        if not (text or calls or results):
            continue
        msgs.append({
            "role": t,
            "ts": rec.get("timestamp", ""),
            "text": _cap(text, cap),
            "toolCalls": [{"name": c["name"], "input": _cap(json.dumps(c["input"], ensure_ascii=False), cap)} for c in calls],
            "toolResults": [_cap(r, cap) for r in results],
        })
    return msgs


def _cap(s: str, cap: int) -> str:
    if s and len(s) > cap:
        return s[:cap] + f"\n… [+{len(s) - cap} chars]"
    return s


def read_memory(dirname: str) -> dict:
    """MEMORY.md index + parsed frontmatter for each memory file."""
    mdir = PROJECTS_DIR / dirname / "memory"
    result = {"indexMd": "", "files": []}
    if not mdir.is_dir():
        return result
    idx = mdir / "MEMORY.md"
    if idx.is_file():
        result["indexMd"] = idx.read_text(encoding="utf-8", errors="replace")
    for f in sorted(mdir.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        raw = f.read_text(encoding="utf-8", errors="replace")
        fm, body = _split_frontmatter(raw)
        result["files"].append({
            "name": f.stem,
            "title": fm.get("name", f.stem),
            "description": fm.get("description", ""),
            "type": fm.get("type", ""),
            "body": body,
        })
    return result


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    fm: dict = {}
    if not raw.startswith("---"):
        return fm, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return fm, raw
    for line in parts[1].splitlines():
        s = line.strip()
        if ":" in s and not s.startswith("#"):
            k, _, v = s.partition(":")
            k, v = k.strip(), v.strip()
            if k in ("name", "description", "type") and v and k not in fm:
                fm[k] = v
    return fm, parts[2].lstrip("\n")
