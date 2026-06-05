# load-bearing: AI Metaphor Discovery & Analysis Tool

`load-bearing` is an automated NLP pipeline that discovers, classifies, and tracks overused metaphorical language and idioms in your AI coding assistant conversation history. 

It currently supports side-by-side parsing and comparison for **Claude Code** and **Gemini/Antigravity** logs.

```
                  ┌──────────────────────────────┐
                  │  Raw JSONL logs from Claude  │
                  │  & Gemini/Antigravity        │
                  └──────────────┬───────────────┘
                                 │ (Extract)
                                 ▼
                     ┌──────────────────────┐
                     │ messages.db (SQLite) │
                     └───────────┬──────────┘
                                 │ (Mine N-Grams)
                                 ▼
                      ┌─────────────────────┐
                      │   candidates.json   │
                      └───────────┬─────────┘
                                 │ (Verify via LLM)
                                 ▼
                 ┌──────────────────────────────┐
                 │ verified_metaphors.json      │
                 └──────────────┬───────────────┘
                                 │ (Aggregate Trends)
                                 ▼
                      ┌─────────────────────┐
                      │ trends.json/js      │
                      └───────────┬─────────┘
                                 │ (Serve)
                                 ▼
                  ┌──────────────────────────────┐
                  │     Interactive Dashboard    │
                  │    http://localhost:8080     │
                  └──────────────────────────────┘
```

## Features
- **Multi-Provider Support**: Side-by-side linguistic extraction for Claude (`~/.claude/projects/`) and Gemini/Antigravity (`~/.gemini/antigravity/brain/`).
- **Unsupervised N-Gram Mining**: Custom tokenization and hyphen-splitting locally to identify candidate idioms.
- **LLM-in-the-Loop Verification**: Semantic validation of candidates using `gpt-5.4-mini` (or fallback models) with contextual sentence examples.
- **Linguistic Trend Tracking**: Relational SQL baselines tracking density (occurrences per 10k words) over months.
- **Self-Contained Dashboard**: Beautiful dark-theme visual UI serving metrics and drill-down transcript highlights without CORS issues.

---

## Installation

Verify you have Python 3.8+ installed, then clone the repository and install the package locally:

```bash
git clone https://github.com/orlenko/load-bearing.git
cd load-bearing
make install
```
*Note: This package uses only the Python standard library for its backend and CLI, meaning it requires zero external python library installations!*

---

## CLI Usage

The tool provides a unified `load-bearing` CLI command:

### 1. Run Complete Analysis (Extract + Mine + Verify + Serve)
Extracts new logs, compiles candidates, calls the OpenAI API to verify metaphors, computes trends, and spins up the dashboard server:
```bash
export OPENAI_API_KEY="your-api-key"
load-bearing run --serve
```
*Or use the Makefile shortcut:*
```bash
make run
```

### 2. Run Quick Trend Update (Extract + Serve, $0.00 Cost)
If you have already run the verification step and just want to update the trend chart for your **existing** metaphors with new conversations:
```bash
load-bearing run-quick --serve
```
*Or use the Makefile shortcut:*
```bash
make run-quick
```

### 3. Spin Up Dashboard Only
Spins up the web server on port `8080` (or another specified port) and opens the dashboard UI:
```bash
load-bearing dashboard --port 8080
```

### 4. Reset Caches
Remove the local SQLite database and JSON data cache files:
```bash
load-bearing clean
```

---

## Configuration & Filtering

### Blacklisting Terms
To ignore specific terms (like custom project keywords or human-introduced vocabulary, e.g., `"hostile eyes"`):
1. Create a `blacklist.txt` file in your current working directory.
2. List the phrases to exclude (one phrase per line, case-insensitive).
3. Run `load-bearing run-quick`. It will immediately filter them out of the compiled trends and update your dashboard visual outputs.
