# Greenlighting Agent User Guide

This guide explains how to run the Greenlighting Agent locally, use the web demo, run CLI analyses, inspect outputs, and troubleshoot common issues.

## 1. Setup

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Optional live-analysis configuration:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
ANTHROPIC_API_KEY=your_anthropic_key_here
TMDB_API_KEY=your_tmdb_key_here
```

Notes:

- `python main.py --sample` does not require API keys.
- Full live LLM synthesis requires `ANTHROPIC_API_KEY`.
- TMDB comparable enrichment requires `TMDB_API_KEY`.
- If TMDB is unavailable, the app still includes comparable rows as input-only fallback data.

## 2. Web Demo

Start the local server:

```bash
uvicorn web_app:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

The web UI supports:

- project description
- budget
- genre
- platform
- target audience
- comparable titles
- TMDB comparable search and selection
- demo-mode toggle
- live agent progress stream
- rendered report preview
- project comparison table from pasted CSV
- Markdown download
- JSON download

Recommended first run:

1. Leave **Demo mode** checked.
2. Click **Load Sample** if the fields are empty.
3. Click **Run Analysis**.
4. Wait for the progress panel to show **Completed**.
5. Review the report preview.
6. Download Markdown or JSON if needed.

Comparable search:

1. Use **Search comparable titles** to search TMDB from the browser.
2. Click **Add** on 2-5 useful titles.
3. The selected titles automatically populate the `Comparables` field.
4. Run the analysis with those selected comparables.

If TMDB is unavailable, the UI returns demo fallback comparables so the workflow is still testable.

Project comparison run:

1. Scroll to **Project Comparison**.
2. Click **Load Batch Sample** or paste CSV rows with the documented batch columns.
3. Click **Run Batch**.
4. Review the comparison table for recommendation, confidence, ROI, risk level, and report links.
5. Download the batch CSV or JSON summary if needed.

## 3. CLI Usage

### No-Key Sample

```bash
python main.py --sample
```

This runs a deterministic sci-fi project and writes a Markdown report, JSON report, and run ledger.

### Live Single-Project Analysis

```bash
python main.py \
  --project "A contained sci-fi thriller about a lunar mining crew and a rogue AI" \
  --budget 18000000 \
  --genre "Science Fiction" \
  --platform hybrid \
  --comparables "Ex Machina,Moon,Arrival" \
  --target-audience "adults 18-49, sci-fi thriller fans"
```

Platform choices:

- `theatrical`
- `streaming`
- `hybrid`

### Batch Mode

Run the included deterministic sample batch:

```bash
python main.py --batch examples/projects.csv --sample
```

Run a live batch:

```bash
python main.py --batch projects.csv
```

CSV columns:

```text
description,budget,genre,platform,comparables,target_audience
```

`comparables` should be comma-separated inside the CSV cell.

### Interactive Mode

```bash
python main.py --interactive
```

Available commands:

```text
/analyze-script <project description>
/market-research <description>
/financial-model <budget>
/risk-assessment <project description>
/help
/exit
```

## 4. Outputs

Reports are written under `outputs/`.

Markdown report:

```text
outputs/reports/project_name_YYYYMMDD_HHMMSS.md
```

Structured JSON report:

```text
outputs/reports/project_name_YYYYMMDD_HHMMSS.json
```

Run ledger:

```text
outputs/runs/project_name_YYYYMMDD_HHMMSS_run.json
```

Batch summaries:

```text
outputs/batches/batch_YYYYMMDD_HHMMSS_summary.csv
outputs/batches/batch_YYYYMMDD_HHMMSS_summary.json
```

The JSON report is useful for dashboards, downstream tools, or later UI work. The run ledger is useful for auditing model usage, estimated cost, TMDB request counts, and report paths.

## 5. Reading The Report

Each report includes:

- final recommendation
- confidence level
- executive summary
- decision drivers
- comparable evidence table
- financial scenario snapshot
- risk matrix
- detailed synthesis
- subagent notes

Recommendation meanings:

- **GO:** strong case to proceed
- **CONDITIONAL GO:** proceed only if the listed conditions are handled
- **NO-GO:** do not proceed based on current evidence

## 6. Report Quality Controls

Before saving a report, the app checks:

- final recommendation matches the synthesis text
- comparable table exists when comparables were supplied
- financial scenario metrics exist when budget is positive
- risk matrix is present
- TMDB fallback is surfaced as a warning

If a mandatory check fails, the report is not saved. If TMDB enrichment fails, the report can still save with an explicit warning and input-only comparable rows.

## 7. Development Checks

Run tests:

```bash
python -m unittest discover -s tests
```

Run compile check:

```bash
PYTHONPYCACHEPREFIX=.pycache python -m compileall main.py web_app.py agents tools utils tests
```

Run setup smoke:

```bash
python test_setup.py
```

## 8. Troubleshooting

### API Key Not Found

Use sample mode if you do not need live model calls:

```bash
python main.py --sample
```

For live analysis, confirm `.env` exists and contains:

```bash
ANTHROPIC_API_KEY=...
```

### TMDB Enrichment Failed

Check:

- `.env` contains `TMDB_API_KEY`
- the key is active
- network access is available
- TMDB rate limits have not been exceeded

The app still runs without TMDB by using input-only comparable evidence.

### Module Not Found

Activate the virtual environment and reinstall:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Web Server Port Already In Use

Run on another port:

```bash
uvicorn web_app:app --host 127.0.0.1 --port 8001
```

Then open:

```text
http://127.0.0.1:8001
```

## 9. Practical Tips

- Include 2-5 comparable titles when possible.
- Use real budget numbers in dollars, not millions.
- Keep project descriptions specific: hook, setting, audience, and production constraints help.
- Use `--sample` before live analysis to confirm local setup.
- Use batch mode to compare multiple project ideas quickly.
