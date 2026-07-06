#!/usr/bin/env python3
"""Generate a synthetic demo dataset (no real data) so retrace can be run against
sample history for screenshots / trying it out.

    python3 demo/seed_demo.py
    RETRACE_CLAUDE_DIR=demo/data/claude \
    RETRACE_CODEX_DIR=demo/data/codex \
    RETRACE_CLINE_DIR=demo/data/cline/data \
        python3 server.py --port 8788 --no-open

All content is fictional (an "acme-store" e-commerce app). Writes to demo/data/
(git-ignored). The keyword "checkout" appears in every provider so a single search
shows Claude + Codex + Cline + a folder source merged under one project.
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "data"
CWD = "/Users/demo/acme-store"          # shared "project" so all providers merge
UUID = "0192abcd-1111-7222-8333-444455556666"


def w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def seed_claude():
    d = ROOT / "claude" / "-Users-demo-acme-store"
    recs = [
        {"type": "ai-title", "aiTitle": "Fix checkout total rounding", "sessionId": UUID},
        {"type": "user", "sessionId": UUID, "cwd": CWD, "gitBranch": "main",
         "timestamp": "2026-07-01T09:15:00Z",
         "message": {"role": "user", "content": "The checkout total is off by a cent on multi-item orders."}},
        {"type": "assistant", "sessionId": UUID, "cwd": CWD, "timestamp": "2026-07-01T09:15:20Z",
         "message": {"role": "assistant", "model": "claude-opus-4-8",
                     "usage": {"output_tokens": 140},
                     "content": [{"type": "text", "text": "Rounding is applied per line item instead of on the summed checkout total. Round once after summing."}]}},
    ]
    w(d / f"{UUID}.jsonl", "\n".join(json.dumps(r) for r in recs))
    # memory
    w(d / "memory" / "MEMORY.md", "# Memory Index\n\n- [Pricing rounds at order level](pricing.md) — round the checkout total once.\n")
    w(d / "memory" / "pricing.md",
      "---\nname: pricing-rounds-at-order-level\ndescription: Round the checkout total once, after summing line items\ntype: project\n---\n\nAlways round the **checkout** total at order level, never per line item.\n")


def seed_codex():
    sess = {"timestamp": "2026-07-02T10:00:00Z", "type": "session_meta",
            "payload": {"id": UUID, "timestamp": "2026-07-02T10:00:00Z", "cwd": CWD}}
    u = {"timestamp": "2026-07-02T10:00:10Z", "type": "response_item",
         "payload": {"type": "message", "role": "user",
                     "content": [{"type": "input_text", "text": "Add a Stripe webhook for the checkout payment_intent.succeeded event."}]}}
    a = {"timestamp": "2026-07-02T10:00:30Z", "type": "response_item",
         "payload": {"type": "message", "role": "assistant",
                     "content": [{"type": "output_text", "text": "I'll add /api/webhooks/stripe, verify the signature, and mark the checkout order paid."}]}}
    f = ROOT / "codex" / "sessions" / "2026" / "07" / "02" / f"rollout-2026-07-02T10-00-00-{UUID}.jsonl"
    w(f, "\n".join(json.dumps(r) for r in (sess, u, a)))
    w(ROOT / "codex" / "session_index.jsonl",
      json.dumps({"id": UUID, "thread_name": "Add Stripe checkout webhook", "updated_at": "2026-07-02T10:00:30Z"}))


def seed_cline():
    base = ROOT / "cline" / "data"
    sid = "1782800000000_demo"
    mp = base / "sessions" / sid / f"{sid}.messages.json"
    msgs = {"version": 1, "updated_at": "2026-07-03T11:00:00Z", "agent": "lead", "sessionId": sid,
            "messages": [
                {"id": "m1", "role": "user", "ts": 1782800000000,
                 "content": [{"type": "text", "text": "Refactor the checkout page to lazy-load the payment form."}]},
                {"id": "m2", "role": "assistant", "ts": 1782800005000,
                 "content": [{"type": "text", "text": "Split the checkout into a shell + a lazily imported PaymentForm; cuts initial JS."}]},
            ]}
    w(mp, json.dumps(msgs, indent=2))
    db = base / "db" / "sessions.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE IF NOT EXISTS sessions (session_id TEXT, source TEXT, cwd TEXT, "
                "workspace_root TEXT, prompt TEXT, updated_at TEXT, started_at TEXT, "
                "messages_path TEXT, model TEXT)")
    con.execute("DELETE FROM sessions")
    con.execute("INSERT INTO sessions (session_id, source, cwd, workspace_root, prompt, updated_at, "
                "started_at, messages_path, model) VALUES (?,?,?,?,?,?,?,?,?)",
                (sid, "cli", CWD, CWD, "Refactor the checkout page", "2026-07-03T11:00:05Z",
                 "2026-07-03T11:00:00Z", str(mp), "cline/deepseek"))
    con.commit()
    con.close()


def seed_notes():
    d = ROOT / "notes"
    w(d / "architecture.md", "# acme-store\n\nThe **checkout** flow: cart -> checkout -> Stripe -> order.\nRound totals at order level.\n")
    w(d / "todo.md", "- [ ] add checkout webhook retry\n- [ ] cache product search\n- [x] fix rounding\n")
    w(d / "spec-checkout.txt", "Checkout spec: taxes computed on subtotal; total rounded once.\n")


if __name__ == "__main__":
    seed_claude()
    seed_codex()
    seed_cline()
    seed_notes()
    print(f"Demo data written to {ROOT}")
    print("Run:")
    print(f"  RETRACE_CLAUDE_DIR={ROOT}/claude \\")
    print(f"  RETRACE_CODEX_DIR={ROOT}/codex \\")
    print(f"  RETRACE_CLINE_DIR={ROOT}/cline/data \\")
    print(f"      python3 server.py --port 8788 --no-open")
    print(f"Then add a folder source in the UI: {ROOT}/notes")
