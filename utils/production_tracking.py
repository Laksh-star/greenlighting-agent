"""Local cumulative actuals snapshots and manual production-constraint history."""

import csv
import hashlib
import io
import json
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from utils.report_library import load_report_detail

MONEY_FIELDS = ("production_spend", "marketing_spend", "gross_revenue", "studio_receipts")
CONSTRAINT_CATEGORIES = ("Cast/Talent", "Location", "Availability", "VFX", "Schedule")
CONSTRAINT_STATUSES = ("Proposed", "Pending", "Confirmed", "Blocked", "Released")
ACTUALS_CSV = "version,as_of,phase,production_spend,marketing_spend,gross_revenue,studio_receipts,notes\n1,2026-10-07,Interim,2500000,500000,1000000,400000,Example cumulative USD snapshot\n"


def cents(value):
    if value is None or value == "":
        return None
    try:
        money = Decimal(str(value))
        if not money.is_finite() or money < 0 or money > Decimal("9999999999999.99") or money != money.quantize(Decimal(".01")):
            raise ValueError("Amounts must be nonnegative USD with at most two decimal places")
        return int(money * 100)
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid USD amount")


def normalize_snapshot(data):
    try:
        version = int(str(data["version"]))
        if version < 1:
            raise ValueError("Version must be positive")
        as_of = date.fromisoformat(str(data["as_of"])).isoformat()
    except (KeyError, TypeError, ValueError):
        raise ValueError("A valid version and as-of date are required")
    phase = data.get("phase", "Interim")
    notes = str(data.get("notes") or "").strip()
    if phase not in ("Interim", "Final") or not notes or len(notes) > 5000:
        raise ValueError("Interim/Final phase and decision notes within 5000 characters are required")
    amounts = {key: cents(data.get(key)) for key in MONEY_FIELDS}
    if all(value is None for value in amounts.values()):
        raise ValueError("At least one actual amount is required; blanks mean unknown")
    return {"version": version, "as_of": as_of, "phase": phase, "notes": notes, **amounts}


def parse_actuals_csv(text):
    if len(text) > 200000:
        raise ValueError("CSV exceeds 200000 characters")
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    expected = {"version", "as_of", "phase", "notes", *MONEY_FIELDS}
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != expected:
        raise ValueError("CSV headers must match the actuals template")
    rows = []
    for index, row in enumerate(reader, 2):
        if len(rows) >= 200:
            raise ValueError("CSV is limited to 200 snapshots")
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"CSV row {index} has missing or extra columns")
        try:
            rows.append(normalize_snapshot(row))
        except ValueError as exc:
            raise ValueError(f"CSV row {index}: {exc}")
    if not rows:
        raise ValueError("CSV contains no snapshots")
    return rows


def save_actuals(store, project_id, rows, source="manual"):
    workspace = store.get(project_id)
    versions = {v["number"] for v in workspace["versions"]}
    if any(row["version"] not in versions for row in rows):
        raise ValueError("Every snapshot must refer to a version of this project")
    imported, skipped = 0, 0
    with store.connect() as db:
        for row in rows:
            fingerprint = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
            cursor = db.execute("INSERT OR IGNORE INTO actual_snapshots (project_id, version, as_of, phase, production_spend, marketing_spend, gross_revenue, studio_receipts, notes, source, fingerprint, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (project_id, row["version"], row["as_of"], row["phase"],
                                 *(row[field] for field in MONEY_FIELDS), row["notes"], source,
                                 fingerprint, datetime.utcnow().isoformat() + "Z"))
            imported += cursor.rowcount
            skipped += 1 - cursor.rowcount
    return {"imported": imported, "skipped_duplicates": skipped}


def save_constraint(store, project_id, data):
    workspace = store.get(project_id)
    if data["version"] not in {v["number"] for v in workspace["versions"]}:
        raise ValueError("Version does not belong to this project")
    if data["category"] not in CONSTRAINT_CATEGORIES or data["status"] not in CONSTRAINT_STATUSES:
        raise ValueError("Invalid production category or status")
    if not data["title"].strip() or not data["notes"].strip():
        raise ValueError("Title and notes are required")
    if len(data["title"]) > 160 or len(data["notes"]) > 5000 or len(data["owner"]) > 120:
        raise ValueError("Constraint text exceeds its limits")
    start, end = data.get("start_date") or "", data.get("end_date") or ""
    if start: date.fromisoformat(start)
    if end: date.fromisoformat(end)
    if start and end and start > end:
        raise ValueError("End date must not precede start date")
    constraint_id = data.get("constraint_id") or uuid.uuid4().hex
    with store.connect() as db:
        if data.get("constraint_id") and not db.execute("SELECT 1 FROM constraint_events WHERE project_id=? AND constraint_id=?", (project_id, constraint_id)).fetchone():
            raise ValueError("Constraint does not belong to this project")
        cursor = db.execute("INSERT INTO constraint_events (project_id, version, constraint_id, category, title, status, owner, start_date, end_date, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (project_id, data["version"], constraint_id, data["category"], data["title"].strip(), data["status"],
                             data["owner"].strip(), start, end, data["notes"].strip(), datetime.utcnow().isoformat() + "Z"))
        return dict(db.execute("SELECT * FROM constraint_events WHERE id=?", (cursor.lastrowid,)).fetchone())


def production_detail(store, project_id, report_dir, snapshot_id=None):
    workspace = store.get(project_id)
    with store.connect() as db:
        snapshots = [dict(row) for row in db.execute("SELECT * FROM actual_snapshots WHERE project_id=? ORDER BY as_of DESC, id DESC", (project_id,))]
        history = [dict(row) for row in db.execute("SELECT * FROM constraint_events WHERE project_id=? ORDER BY id DESC", (project_id,))]
    for row in snapshots:
        for key in MONEY_FIELDS:
            row[key] = row[key] / 100 if row[key] is not None else None
        row.pop("fingerprint", None)
    seen, constraints = set(), []
    for event in history:
        if event["constraint_id"] not in seen:
            constraints.append(event)
            seen.add(event["constraint_id"])
    comparison = None
    if snapshots:
        latest = next((s for s in snapshots if s["id"] == snapshot_id), None) if snapshot_id else snapshots[0]
        if latest is None:
            raise ValueError("Snapshot does not belong to this project")
        version = next(v for v in workspace["versions"] if v["number"] == latest["version"])
        payload = load_report_detail(report_dir, version["report_id"])["payload"]
        forecast = payload.get("financial_scenarios", {})
        assumptions = payload.get("financial_assumptions", {})
        streaming = payload.get("project", {}).get("platform") == "streaming"
        from agents.financial_model import normalize_financial_assumptions
        normalized = normalize_financial_assumptions(assumptions, budget=payload.get("project", {}).get("budget", 0), platform=payload.get("project", {}).get("platform", "theatrical"))
        baseline = {"production_spend": payload.get("project", {}).get("budget"),
                    "marketing_spend": normalized["marketing_spend"],
                    "gross_revenue": None if streaming else forecast.get("moderate_revenue"),
                    "studio_receipts": None if streaming else forecast.get("moderate_net_revenue")}
        rows = [{"field": key, "actual": latest[key], "forecast": baseline[key],
                 "variance": round(latest[key] - baseline[key], 2) if latest[key] is not None and baseline[key] is not None else None} for key in MONEY_FIELDS]
        spend = latest["production_spend"] + latest["marketing_spend"] if latest["production_spend"] is not None and latest["marketing_spend"] is not None else None
        profit = latest["studio_receipts"] - spend if latest["studio_receipts"] is not None and spend is not None else None
        comparison = {"snapshot": latest, "report_id": version["report_id"], "version_label": version["label"],
                      "rows": rows, "cash_profit": round(profit, 2) if profit is not None else None,
                      "cash_roi": round(profit / spend * 100, 2) if profit is not None and spend > 0 else None,
                      "warnings": (["Interim cumulative totals are partial; unused budget is not final savings."] if latest["phase"] == "Interim" else []) +
                                  (["Subscriber lifetime value is excluded from cash receipt comparisons."] if streaming else [])}
    elif snapshot_id:
        raise ValueError("Snapshot does not belong to this project")
    return {"actual_snapshots": snapshots, "comparison": comparison, "constraints": constraints,
            "constraint_history": history, "blocker_count": sum(c["status"] == "Blocked" for c in constraints)}
