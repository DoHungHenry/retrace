#!/usr/bin/env python3
"""retrace — local, zero-dependency search across AI coding history + your files.

Unifies Claude Code, Codex, and Cline session history (plus any local folder you add)
into one search-first web app, grouped by real project. Read-only; nothing leaves your machine.

Run:  python3 server.py            # auto-picks a free port
      python3 server.py --port 8787 --no-open

Footprint: ~25 MB idle (stdlib http.server); search shells out to ripgrep (~1 MB,
transient) with a pure-Python fallback. No index, no external packages.
"""
from __future__ import annotations

import argparse
import json
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import parser
import codex
import cline
import sources as filesrc
import search

STATIC_DIR = Path(__file__).parent / "static"
_CONTENT_TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence per-request stderr noise
        pass

    def do_GET(self):
        u = urlparse(self.path)
        route = u.path
        q = parse_qs(u.query)
        try:
            if route == "/" or route == "/index.html":
                self._static("index.html")
            elif route.startswith("/static/"):
                self._static(route[len("/static/"):])
            elif route == "/api/projects":
                self._json(_merged_projects())
            elif route == "/api/sessions":
                self._json(_sessions(_one(q, "provider"), _one(q, "project")))
            elif route == "/api/session":
                self._json(_transcript(_one(q, "provider"), _one(q, "project"), _one(q, "id")))
            elif route == "/api/memory":
                self._json(parser.read_memory(_one(q, "project")))  # memory is Claude-only
            elif route == "/api/sources":
                self._json(filesrc.list_sources())
            elif route == "/api/sources/add":
                self._json(filesrc.add_source(_one(q, "label"), _one(q, "path"), _one(q, "glob")))
            elif route == "/api/sources/remove":
                self._json(filesrc.remove_source(_one(q, "id")))
            elif route == "/api/file":
                data = filesrc.read_file(_one(q, "path"))
                self._json(data) if data else self._err(403, "not an allowed file")
            elif route == "/api/reveal":
                self._json(filesrc.reveal(_one(q, "path")))
            elif route == "/api/search":
                self._json(search.search(
                    query=_one(q, "q"),
                    projects=_multi(q, "project"),
                    sources=_multi(q, "source"),
                    roles=_multi(q, "role"),
                    since=_one(q, "since"),
                    until=_one(q, "until"),
                    whole_word=_one(q, "word") != "0",
                    match_mode=(_one(q, "mode") or "and").lower(),
                    min_matches=max(1, int(_one(q, "min") or 1)),
                    providers=_multi(q, "provider"),
                ))
            else:
                self._err(404, "not found")
        except BrokenPipeError:
            pass
        except Exception as e:  # never crash the server on one bad request
            self._err(500, str(e))

    def _static(self, rel: str):
        f = (STATIC_DIR / rel).resolve()
        if STATIC_DIR.resolve() not in f.parents or not f.is_file():
            return self._err(404, "not found")
        body = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _CONTENT_TYPES.get(f.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code: int, msg: str):
        body = json.dumps({"error": msg}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _merged_projects() -> list:
    """One entry per real working directory, merging all providers' projects under it."""
    merged: dict = {}
    for p in parser.list_projects() + codex.list_projects() + cline.list_projects():
        key = (p["realPath"] or "").rstrip("/") or p["realPath"]
        m = merged.get(key)
        if m is None:
            m = merged[key] = {"realPath": key, "providers": {}, "sessionCount": 0,
                               "lastActivity": 0.0, "hasMemory": False}
        m["providers"][p["provider"]] = {"dir": p["dir"], "sessionCount": p["sessionCount"]}
        m["sessionCount"] += p["sessionCount"]
        m["lastActivity"] = max(m["lastActivity"], p["lastActivity"])
        m["hasMemory"] = m["hasMemory"] or p["hasMemory"]
    out = list(merged.values())
    out.sort(key=lambda m: m["lastActivity"], reverse=True)
    return out


_SESSIONS = {"codex": codex.session_list, "cline": cline.session_list}
_TRANSCRIPTS = {"codex": codex.transcript, "cline": cline.transcript}


def _sessions(provider: str, project: str) -> list:
    return _SESSIONS.get(provider, parser.session_list)(project)


def _transcript(provider: str, project: str, session_id: str) -> list:
    return _TRANSCRIPTS.get(provider, parser.transcript)(project, session_id)


def _one(q: dict, k: str) -> str:
    return (q.get(k) or [""])[0]


def _multi(q: dict, k: str) -> list[str]:
    vals = q.get(k) or []
    out = []
    for v in vals:
        out += [x for x in v.split(",") if x]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0, help="0 = auto-pick a free port")
    ap.add_argument("--no-open", action="store_true", help="do not open the browser")
    args = ap.parse_args()

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    port = httpd.server_address[1]
    url = f"http://127.0.0.1:{port}"
    engine = "ripgrep" if search._RG else "python-fallback"
    print(f"Claude history viewer  →  {url}")
    print(f"  projects dir: {parser.PROJECTS_DIR}")
    print(f"  search engine: {engine}")
    print("  Ctrl+C to stop.")
    if not args.no_open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
