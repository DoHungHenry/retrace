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

## Role — who said it

Both **off** by default — and this is the one asymmetry worth knowing:

> **Off = no role filter** (both speakers included). Turning one on narrows to *just* that speaker.

| Chip | Keeps only |
|---|---|
| **User** | Lines you typed |
| **Assistant** | The AI's replies |

## Matching behavior

| Chip | Effect |
|---|---|
| **Whole word** | `stage` matches only the word `stage`, not `staged` / `stages`. Off = substring match. The single biggest noise reducer. |
| **All words** | Multi-keyword logic. `All words` = **AND** (every keyword must appear). Click it to flip to **Any word** = **OR** (any keyword matches). |
| **Hide 1-hit** | Drops files that mention the term only **once** (incidental). Keeps files with 2+ hits. |

## Date range

Two `dd/mm/yyyy` inputs = **from** / **to**. Filter results by session timestamp. Both empty = no date limit.

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

## Which do you actually need?

For day-to-day searching:

- **Whole word** — biggest noise reducer
- **Provider chips** — focus one tool
- **Hide 1-hit** — cut incidental mentions

Rarely needed:

- **Role** — only when you want just your prompts vs just the AI's answers
- **Date range** — time-boxing an investigation
- **Memory** off — if you only care about transcripts
