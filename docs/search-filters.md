# Search filters & controls

Every control in the filter bar, left to right. **Blue outline = on**, grey = off.

Most are toggles that narrow your search; a few change *how* matching works. Defaults are
tuned so a plain search "just works" — you only touch these to focus or reduce noise.

---

## Provider — which tool's history

All **on** by default. Turn one off to exclude it.

| Chip | Searches |
|---|---|
| **Claude** | Claude Code sessions |
| **Codex** | Codex sessions |
| **Cline** | Cline sessions |
| **Files** | Your custom folder sources (added spaces), searched as raw files |

## Source — which part of Claude data

Both **on** by default.

| Chip | Searches |
|---|---|
| **History** | Conversation transcripts |
| **Memory** | The `memory/*.md` files (persistent facts) |

> **Browse a project's memory** — click the **◆** button on a project in the sidebar to open *all* its memory files at once (no keyword needed). Only projects that have memory show the ◆.

## Matching behavior

| Chip | Effect |
|---|---|
| **Whole word** | `stage` matches only the word `stage`, not `staged` / `stages`. Off = substring match. The single biggest noise reducer. |

Multiple keywords are matched as **AND** — every keyword must appear in a file for it to show.

---

## Sort & Group

Two dropdowns to the right of the dates.

**Sort** orders results (and drives which land on each page):

| Option | Order |
|---|---|
| Relevance *(default)* | Most keyword hits first, then most recent |
| Newest / Oldest | By session timestamp |
| Space | By project path (A–Z) |
| Provider | By tool (A–Z) |

**Group** clusters results under headers:

| Option | Groups by |
|---|---|
| None *(default)* | Flat list |
| Provider | Claude / Codex / Cline / Files |
| Space | Project |
| Source | History / Memory / File |

Click a group header to **collapse / expand** it.

---

## Everyday use

- **Whole word** — biggest noise reducer
- **Provider chips** — focus one tool
- **Memory** off — if you only care about transcripts
- **Sort / Group** — organize a large result set
