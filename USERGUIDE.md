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
- optional script/treatment text or Markdown upload
- budget
- genre
- platform
- target audience
- comparable titles
- TMDB comparable search and selection
- private dataset save/search mode
- financial assumption controls
- demo-mode toggle
- live agent progress stream
- rendered report preview
- report history for previous local runs
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

Script/treatment input:

1. Open **Script / treatment** under the project description.
2. Upload a `.txt` or `.md` file, or paste treatment/script text directly.
3. Run the analysis. The creative assessment receives the source-material excerpt, and the report includes a source-material snapshot.

Full source text is used during the run. Saved JSON and run ledgers keep only the source name, excerpt, and counts.

Comparable search:

1. Use **Search comparable titles** to search TMDB from the browser.
2. Click **Add** on 2-5 useful titles.
3. The selected titles automatically populate the `Comparables` field.
4. Run the analysis with those selected comparables.

If TMDB is unavailable, the UI returns demo fallback comparables so the workflow is still testable.

Private dataset mode:

1. Open **Private dataset** inside the comparable search panel.
2. Click **Load Sample Dataset** or paste a studio CSV.
3. Give it a dataset name and click **Save Dataset**.
4. Change **Source** to `Private Dataset` or `Private + TMDB`.
5. Search/select comparable titles.
6. Run the analysis. Private rows are used as comparable evidence and clearly labeled in the report.

Private dataset columns:

```text
title,year,genre,platform,budget,marketing_spend,revenue,rating,popularity,audience,territory,notes
```

Saved private datasets are local files under `data/private/` and are ignored by git.

Financial assumptions:

1. Open **Financial assumptions** under the comparable search panel.
2. Adjust P&A, distribution fee, theatrical share, streaming/license value, or scenario multiples.
3. Choose a risk tolerance: `Balanced`, `Conservative`, or `Aggressive`.
4. Run the analysis. The report includes model assumptions, sensitivity rows, scenario comparison, and break-even analysis.

Leave scenario multiples at `0` to use genre defaults. Enter explicit values when you want to test a studio finance case.

Scenario comparison:

1. Run a project analysis with a budget greater than zero.
2. Review **Scenario Comparison** below the report preview.
3. Compare conservative, base, and aggressive cases for exposure, break-even, base revenue/subscribers, net revenue, and ROI.

Report history:

1. Scroll to **Report History**.
2. Click **Refresh History** if you generated reports after opening the page.
3. Click **Open** to preview an older report.
4. Select multiple **Compare** checkboxes and click **Compare Selected** for a side-by-side table.
5. Use **Brief** to download a compact studio decision memo.
6. Use **Print** to open a printable studio memo, then use browser print to save a PDF.
7. Use **Package** to download a zip bundle with the full report, JSON, brief, printable memo, assumptions, scenarios, and evidence.
8. Use **Markdown** or **JSON** links to download the saved artifacts.

Slate dashboard:

1. Scroll to **Slate Dashboard**.
2. Use **Refresh Slate** after new runs to recalculate portfolio metrics.
3. Review recommendation mix, risk mix, platform mix, budget exposure, and ranked candidates from saved local reports.

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
  --target-audience "adults 18-49, sci-fi thriller fans" \
  --source-file treatment.md \
  --marketing-spend 9000000 \
  --base-revenue-multiplier 2.6 \
  --risk-tolerance balanced
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
- source material snapshot, when supplied
- comparable evidence table
- model assumptions
- financial scenario snapshot
- sensitivity table
- break-even analysis
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
## Project Versions In Studio Lot

### Evidence, Stress And Development

Select a saved project at `/lot`. Below its report actions, you will find:

- **Evidence provenance:** source labels, dataset identifiers, retained retrieval
  dates, missing financial evidence warnings and driver support. Unknown older
  sources/dates remain unknown. Unsupported narrative claims are not citations.
- **Financial stress test:** adjust revenue/value multiplier, production overrun
  and marketing spend, then click Calculate stress case. No AI or TMDB calls are
  made. The ROI threshold signal is not a revised recommendation or approval.
  Forecast demand stays fixed when production costs rise; license value stays
  fixed. Streaming results may represent subscriber value, not cash receipts.
- **Development milestones:** record Treatment, Script, Packaging, Financing or
  Production readiness as Not started, In progress, Blocked or Complete, with
  an owner, optional due date and required notes. Updates retain history and the
  reference version. Older standalone reports are linked to a workspace first.

Milestones are project-level manual records, not proof of financing or production
readiness; new analysis versions do not automatically reset them. Owner names
are not authenticated and due dates do not create reminders. Stress cases are
temporary calculations and do not update saved versions. New Markdown/JSON
reports include provenance automatically; older reports are inspected without
rewriting their files.

### Slate Budget Planner

Open `/slate-planner` (or **Budget planner** in the Studio Lot header). Set a
funding cap in USD and select saved projects. The cap includes total modeled
exposure, not just production budget. Each workspace contributes its latest
version once; standalone reports remain independent projects.

The summary shows exposure, remaining funds or overage, exposure-weighted ROI,
modeled profit scenarios, and genre concentration. Missing scenario data is
labelled unavailable with coverage counts, never counted as zero. A manual
selection can exceed the cap, but the overage is flagged.

**Suggest budget-fit slate** uses a ranked greedy selection: approved current
versions first, then AI GO before CONDITIONAL GO, higher base ROI, and lower
risk. It excludes Hold, Rework, Passed, AI NO-GO, negative-base-ROI, and incomplete
financial candidates. It is not an optimal portfolio or an approval action;
review conditions and unreviewed projects yourself.

**Download plan JSON** captures the selection, version/report IDs, numbers, and
warnings. Plans are not otherwise persisted yet. Estimates assume independent
projects with no diversification, correlation, or release-timing adjustments.
Streaming modeled value can include subscriber lifetime value rather than cash.

### Producer Decisions

Select a saved project in Studio Lot. Near the top of its details, open
**Record producer decision**. Choose the reviewed version and Approved, Hold,
Rework, or Passed. Enter the reviewer name and decision notes; conditions are
optional. Click **Save producer decision**. Legacy standalone reports are linked
to a workspace when you open this action; illustrative sample stages cannot
receive decisions.

Decisions are separate from the AI recommendation and never change report
contents, roof colours, or financial forecasts. Each save adds a dated history
entry. The latest decision on the current version is shown; a newer analysis
version awaits its own review. Older approvals are labelled as applying only to
their reviewed version. Conditions are recorded text, not automatically enforced.
Reviewer names are self-entered, not authenticated identities. This remains a
local workflow, not a multi-user approval or legal sign-off system.

### Analyze Versions


At `/lot`, enter a project name and version name when pitching. After analysis,
select its soundstage and click **Reanalyze**. Revise the inputs, name the new
version, check Demo mode, and submit. Each successful run is saved separately.

Use **Open version** to inspect an earlier brief and the **Before** / **After**
selectors to compare inputs and outcomes. Studio Lot totals use each project's
latest completed version; report history in the classic UI still includes every
report. Older standalone reports become workspaces when you choose Reanalyze.

Full treatment text is retained locally for new workspace versions. Older
reports may have only an excerpt and require you to paste the treatment again.
Back up `outputs/projects/` together with `outputs/reports/`. Neither should be
published to GitHub. See [STUDIO_LOT.md](STUDIO_LOT.md#project-workspaces).

## Actuals And Production Constraints

Select a project's soundstage in Studio Lot, then click **Actuals**. Open
**Record cumulative snapshot**, choose the forecast version, date and reporting
phase, enter known USD totals and notes, then save. Leave unknown fields blank;
enter zero only when confirmed. Production/marketing spend, gross revenue and
studio cash receipts are separate. The table compares cumulative actuals against
the chosen version's full forecast, not a time-adjusted forecast. Interim
underspend is not final savings. Cash ROI requires both cost totals and receipts.
Streaming subscriber lifetime value is not treated as forecast cash receipts.

Use **Snapshot history** to review an earlier snapshot. Corrections append a
new snapshot for the same date; the newest record for the newest as-of date is
shown by default. Totals are never summed across snapshots. Exact duplicates
are skipped. **Import actuals CSV** provides a template; it accepts up to 200
rows, at most 200 KB, USD with up to two decimal places and existing version
numbers. Invalid rows or unknown versions reject the entire import.

Click **Production**, then **Add or update constraint**. Choose Cast/Talent,
Location, Availability, VFX or Schedule, add title, owner/contact, optional date
window and notes. Status can be Proposed, Pending, Confirmed, Blocked or Released.
Choose an existing constraint to update it; previous entries remain in
**Constraint history**. Updates refer to the project's latest analysis version.
Blockers do not change the AI report or approve/reject the project.

These records are manually supplied local evidence, not audited accounts,
verified talent availability, automated scheduling or booking. No API keys are
needed. Demo analyses can be used to try the workflow, but their forecasts remain
sample data. Keep the workspace database and linked reports together in backups.
