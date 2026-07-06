"""Full-text search across providers (Claude Code + Codex), history + memory.

Prefers ripgrep (no index, always fresh); pure-Python fallback if absent. Results are
GROUPED by session/memory file. Multi-keyword AND/OR. Per-provider adapters keep each
tool's schema isolated — add a new provider by writing one adapter module + a branch here.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import parser as claude
import codex
import cline
import sources as filesrc
from datetime import datetime, timezone

CLAUDE_ROOT = claude.PROJECTS_DIR
CODEX_ROOT = codex.SESSIONS_ROOT
CLINE_ROOT = cline.SESSIONS_DIR
ALL_PROVIDERS = ["claude", "codex", "cline", "files"]

_RG_CANDIDATES = [
    "/opt/homebrew/bin/rg",   # macOS (Homebrew)
    "/usr/local/bin/rg",      # macOS (Intel) / common
    "/usr/bin/rg",            # Linux (apt/dnf)
]


def find_rg() -> str | None:
    which = shutil.which("rg")
    if which:
        return which
    for c in _RG_CANDIDATES:
        if Path(c).is_file():
            return c
    return None


_RG = find_rg()


def _engine() -> str:
    return "ripgrep" if _RG else "python"


def search(query: str, projects: list[str], sources: list[str],
           roles: list[str], since: str, until: str,
           whole_word: bool = True, match_mode: str = "and",
           min_matches: int = 1, providers: list[str] | None = None,
           limit: int = 150) -> dict:
    """Search selected providers, group hits by file, combine keywords by AND/OR."""
    query = (query or "").strip()
    keywords = query.split()
    if not keywords:
        return {"results": [], "engine": _engine(), "truncated": False}

    prov_sel = [p for p in (providers or ALL_PROVIDERS) if p in ALL_PROVIDERS] or ALL_PROVIDERS
    want_history = not sources or "history" in sources
    want_memory = not sources or "memory" in sources
    project_set = set(projects)
    role_set = set(roles)

    groups: dict[str, dict] = {}
    for kw in keywords:
        if "claude" in prov_sel:
            globs = []
            if want_history:
                globs += ["--glob", "*.jsonl"]
            if want_memory:
                globs += ["--glob", "**/memory/*.md"]
            if globs:
                for m in _matches(kw, CLAUDE_ROOT, globs, whole_word):
                    _add(groups, m, _claude_result(m, kw, whole_word), kw)
        if "codex" in prov_sel and want_history:
            for m in _matches(kw, CODEX_ROOT, ["--glob", "*.jsonl"], whole_word):
                _add(groups, m,
                     codex.parse_match(m["path"], m["line"], kw, whole_word, _find_pos, _snippet_at),
                     kw)
        if "cline" in prov_sel and want_history:
            # Cline stores one whole-JSON transcript per file → dedupe candidate files,
            # then scan each file's messages (rg only selects which files to open).
            seen = set()
            for m in _matches(kw, CLINE_ROOT, ["--glob", "*.messages.json"], whole_word):
                if m["path"] in seen:
                    continue
                seen.add(m["path"])
                for r in cline.parse_file(m["path"], kw, whole_word, _find_pos, _snippet_at):
                    _add(groups, {"path": m["path"]}, r, kw)
        if "files" in prov_sel:
            for s in filesrc.list_sources():
                globs = []
                for g in (s.get("glob") or "").split(","):
                    g = g.strip()
                    if g:
                        globs += ["--glob", g]
                # (a) content matches — only works for text files
                for m in _matches(kw, Path(s["path"]), globs, whole_word):
                    _add(groups, m, _files_result(m, s, kw, whole_word), kw)
                # (b) filename matches — finds ANY file by name (docx/xlsx/pdf incl.)
                for fp in _list_files(Path(s["path"]), globs):
                    _add(groups, {"path": fp}, _filename_result(fp, s, kw, whole_word), kw)

    kwset = set(keywords)
    out = []
    for g in groups.values():
        if match_mode == "and" and g["kw"] != kwset:
            continue
        if g["count"] < min_matches:
            continue
        if project_set and g["project"] not in project_set:
            continue
        if not want_history and g["source"] == "history":
            continue
        if not want_memory and g["source"] == "memory":
            continue
        if role_set and not (g["roles"] & role_set):
            continue
        ts = g["ts"] or ""
        if since and ts and ts < since:
            continue
        if until and ts and ts > until + "T23:59:59Z":
            continue
        out.append({
            "provider": g["provider"], "project": g["project"], "locator": g["locator"],
            "source": g["source"], "sessionId": g["sessionId"], "file": g["file"],
            "ts": g["ts"], "count": g["count"], "keywords": sorted(g["kw"]),
            "snippets": [{"kw": k, "text": g["snips"][k]} for k in sorted(g["snips"])],
            "title": "", "path": g["path"],
        })

    out.sort(key=lambda r: (r["count"], r["ts"] or ""), reverse=True)
    truncated = len(out) > limit
    out = out[:limit]
    for r in out:
        r["title"] = _title_of(r)
    return {"results": out, "engine": _engine(), "truncated": truncated,
            "keywords": keywords, "mode": match_mode}


def _add(groups: dict, m: dict, r: dict | None, kw: str) -> None:
    if r is None:
        return
    g = groups.get(m["path"])
    if g is None:
        g = groups[m["path"]] = {
            "path": m["path"], "provider": r["provider"], "project": r["project"],
            "locator": r.get("locator", r["project"]), "source": r["source"],
            "sessionId": r["sessionId"], "file": r["file"], "ts": r["ts"],
            "count": 0, "roles": set(), "kw": set(), "snips": {},
        }
    g["count"] += 1
    g["roles"].add(r["role"])
    g["kw"].add(kw)
    if r["ts"] and r["ts"] > g["ts"]:
        g["ts"] = r["ts"]
    g["snips"].setdefault(kw, r["snippet"])


# ---------- matching (ripgrep + python fallback) ----------
def _matches(query: str, root: Path, globs: list[str], whole_word: bool) -> list[dict]:
    if not Path(root).exists():
        return []
    return _rg(query, root, globs, whole_word) if _RG else _py(query, root, globs, whole_word)


def _rg(query: str, root: Path, globs: list[str], whole_word: bool) -> list[dict]:
    word = ["-w"] if whole_word else []
    cmd = [_RG, "--json", "-i", "--fixed-strings", *word, "-e", query, *globs, str(root)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    except (subprocess.SubprocessError, OSError):
        return []
    out = []
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "match":
            d = obj["data"]
            out.append({"path": d["path"]["text"], "line": d["lines"]["text"]})
    return out


def _py(query: str, root: Path, globs: list[str], whole_word: bool) -> list[dict]:
    root = Path(root)
    pats = [globs[i + 1] for i, g in enumerate(globs) if g == "--glob"]
    files: list[Path] = []
    for pat in pats:
        files += root.rglob(pat.replace("**/", ""))
    rx = re.compile(r"\b" + re.escape(query) + r"\b", re.I) if whole_word else None
    ql = query.lower()
    out = []
    for f in files:
        try:
            with f.open(encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if (rx.search(line) if rx else ql in line.lower()):
                        out.append({"path": str(f), "line": line})
                        if len(out) > 3000:
                            return out
        except OSError:
            continue
    return out


# ---------- Claude result parsing (validated against clean text) ----------
def _claude_result(match: dict, query: str, whole_word: bool) -> dict | None:
    path = Path(match["path"])
    encoded_dir = _project_of(path)            # locator: how to reopen (PROJECTS_DIR/<dir>)
    real = _claude_realpath(encoded_dir)       # canonical project = real working directory
    if path.suffix == ".md":  # memory hit
        text = match["line"]
        pos = _find_pos(text, query, whole_word)
        if pos < 0:
            return None
        return {"provider": "claude", "project": real, "locator": encoded_dir,
                "source": "memory", "role": "memory", "ts": "", "sessionId": "",
                "file": path.name, "snippet": _snippet_at(text, pos, len(query))}
    try:
        rec = json.loads(match["line"])
    except json.JSONDecodeError:
        return None
    if rec.get("type") not in ("user", "assistant"):
        return None
    text, calls, results = claude._block_text(rec.get("message", {}).get("content"))
    parts = [text]
    if calls:
        parts.append(json.dumps(calls, ensure_ascii=False))
    parts.extend(results)
    hay = "\n".join(p for p in parts if p)
    pos = _find_pos(hay, query, whole_word)
    if pos < 0:
        return None
    return {"provider": "claude", "project": real, "locator": encoded_dir, "source": "history",
            "role": rec["type"], "ts": rec.get("timestamp", ""),
            "sessionId": rec.get("sessionId", "") or path.stem,
            "file": path.name, "snippet": _snippet_at(hay, pos, len(query))}


def _file_iso(p: Path) -> str:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except OSError:
        return ""


def _rel(p: Path, root: str) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return p.name


def _files_result(match: dict, source: dict, query: str, whole_word: bool) -> dict | None:
    """Content hit — the matched raw line IS the content (text files only)."""
    text = match["line"]
    pos = _find_pos(text, query, whole_word)
    if pos < 0:
        return None
    p = Path(match["path"])
    return {"provider": "files", "project": source["path"], "locator": str(p),
            "source": "file", "role": "file", "ts": _file_iso(p), "sessionId": str(p),
            "file": _rel(p, source["path"]), "snippet": _snippet_at(text, pos, len(query))}


def _filename_result(fp: str, source: dict, query: str, whole_word: bool) -> dict | None:
    """Name hit — matches the file's relative path, so binary docs (docx/xlsx/pdf) are findable."""
    p = Path(fp)
    rel = _rel(p, source["path"])
    pos = _find_pos(rel, query, whole_word)
    if pos < 0:
        return None
    return {"provider": "files", "project": source["path"], "locator": fp,
            "source": "filename", "role": "file", "ts": _file_iso(p), "sessionId": fp,
            "file": rel, "snippet": "📄 " + rel}


def _list_files(root: Path, globs: list[str]) -> list[str]:
    """File list under a source (respects .gitignore via `rg --files`); glob-filtered."""
    if not root.exists():
        return []
    if _RG:
        try:
            proc = subprocess.run([_RG, "--files", *globs, str(root)],
                                  capture_output=True, text=True, timeout=15)
            return proc.stdout.splitlines()
        except (subprocess.SubprocessError, OSError):
            return []
    pats = [globs[i + 1] for i, g in enumerate(globs) if g == "--glob"] or ["*"]
    out = []
    for pat in pats:
        out += [str(x) for x in root.rglob(pat.replace("**/", "")) if x.is_file()]
    return out


def _project_of(path: Path) -> str:
    try:
        return path.relative_to(CLAUDE_ROOT).parts[0]
    except ValueError:
        return path.parent.name


def _claude_realpath(encoded_dir: str) -> str:
    """Real working dir for a Claude project — same source the rail uses, so a session's
    canonical project matches its rail entry (cached in parser)."""
    return claude._real_path_for_project(CLAUDE_ROOT / encoded_dir).rstrip("/")


# ---------- titles ----------
_title_cache: dict[str, tuple[float, str]] = {}


def _title_of(r: dict) -> str:
    if r["source"] == "memory":
        return r["file"]
    if r["provider"] == "codex":
        return codex.title_for(Path(r["path"]))
    if r["provider"] == "cline":
        return cline.title_for(r["sessionId"])
    if r["provider"] == "files":
        return r["file"]
    return _claude_title(r)


def _claude_title(r: dict) -> str:
    p = r["path"]
    try:
        mt = Path(p).stat().st_mtime
    except OSError:
        return r["sessionId"][:8]
    hit = _title_cache.get(p)
    if hit and hit[0] == mt:
        return hit[1] or r["sessionId"][:8]
    title = ""
    try:  # scan only ai-title lines; avoid full-record parse of a big file
        with open(p, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if '"ai-title"' in line:
                    try:
                        title = json.loads(line).get("aiTitle") or title
                    except json.JSONDecodeError:
                        pass
    except OSError:
        pass
    _title_cache[p] = (mt, title)
    return title or r["sessionId"][:8]


# ---------- snippet helpers (shared by all providers) ----------
def _find_pos(text: str, query: str, whole_word: bool) -> int:
    if not text:
        return -1
    if whole_word:
        m = re.search(r"\b" + re.escape(query) + r"\b", text, re.IGNORECASE)
        return m.start() if m else -1
    return text.lower().find(query.lower())


def _snippet_at(text: str, pos: int, qlen: int, window: int = 160) -> str:
    start = max(0, pos - window // 2)
    end = min(len(text), pos + qlen + window)
    pre = "…" if start > 0 else ""
    post = "…" if end < len(text) else ""
    return f"{pre}{text[start:end].strip()}{post}"
