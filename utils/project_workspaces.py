"""Persistent project identities and immutable report-version links."""

import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

from utils.report_library import list_report_summaries, load_report_detail


class ProjectWorkspaces:
    def __init__(self, database: Path):
        self.database = database

    @contextmanager
    def connect(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS versions (
                project_id TEXT NOT NULL REFERENCES projects(id),
                number INTEGER NOT NULL, label TEXT NOT NULL,
                report_id TEXT NOT NULL UNIQUE, request_json TEXT NOT NULL,
                PRIMARY KEY (project_id, number)
            );
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL, version INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Approved', 'Hold', 'Rework', 'Passed')),
                reviewer TEXT NOT NULL, notes TEXT NOT NULL, conditions TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id, version) REFERENCES versions(project_id, number)
            );
        """)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, name, report_id=None, request=None):
        with self.connect() as db:
            if report_id:
                existing = db.execute("SELECT project_id FROM versions WHERE report_id=?", (report_id,)).fetchone()
                if existing:
                    return existing[0]
            project_id = uuid.uuid4().hex
            db.execute("INSERT INTO projects VALUES (?, ?, ?)",
                       (project_id, name, datetime.utcnow().isoformat()))
            if report_id:
                db.execute("INSERT INTO versions VALUES (?, 1, ?, ?, ?)",
                           (project_id, "Original", report_id, json.dumps(request or {})))
            return project_id

    def get(self, project_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not row:
                raise FileNotFoundError("Project not found")
            versions = db.execute("SELECT * FROM versions WHERE project_id=? ORDER BY number DESC", (project_id,)).fetchall()
            decisions = [dict(d) for d in db.execute(
                "SELECT * FROM decisions WHERE project_id=? ORDER BY id DESC", (project_id,))]
        return {**dict(row), "decisions": decisions, "versions": [
            {"number": v["number"], "label": v["label"], "report_id": v["report_id"],
             "request": json.loads(v["request_json"])} for v in versions]}

    def record_decision(self, project_id, version, status, reviewer, notes, conditions=""):
        self.get(project_id)
        if status not in ("Approved", "Hold", "Rework", "Passed"):
            raise ValueError("Invalid producer decision")
        reviewer, notes, conditions = reviewer.strip(), notes.strip(), conditions.strip()
        if not reviewer or not notes:
            raise ValueError("Reviewer and decision notes are required")
        if len(reviewer) > 120 or len(notes) > 5000 or len(conditions) > 5000:
            raise ValueError("Decision text is too long")
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM versions WHERE project_id=? AND number=?", (project_id, version)).fetchone():
                raise ValueError("Version does not belong to this project")
            cursor = db.execute(
                "INSERT INTO decisions (project_id, version, status, reviewer, notes, conditions, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project_id, version, status, reviewer, notes, conditions, datetime.utcnow().isoformat() + "Z"))
            return dict(db.execute("SELECT * FROM decisions WHERE id=?", (cursor.lastrowid,)).fetchone())

    def add_version(self, project_id, report_id, label, request):
        self.get(project_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            number = db.execute("SELECT COALESCE(MAX(number), 0)+1 FROM versions WHERE project_id=?", (project_id,)).fetchone()[0]
            db.execute("INSERT INTO versions VALUES (?, ?, ?, ?, ?)",
                       (project_id, number, label or f"Version {number}", report_id, json.dumps(request)))
        return number

    def slate(self, report_dir):
        # Group before limiting: an older project must not disappear behind its revisions.
        reports = list_report_summaries(report_dir, limit=None)
        by_id = {report["id"]: report for report in reports}
        with self.connect() as db:
            links = {row["report_id"]: dict(row) for row in db.execute(
                "SELECT v.*, p.name FROM versions v JOIN projects p ON p.id=v.project_id")}
        seen, rows = set(), []
        for report in reports:
            link = links.get(report["id"])
            identity = link["project_id"] if link else report["id"]
            if identity in seen:
                continue
            if link:
                workspace = self.get(identity)
                versions = workspace["versions"]
                # Version number, not file modification time, determines the current analysis.
                latest = by_id.get(versions[0]["report_id"], report)
                report = {**latest, "project_name": link["name"], "workspace_id": identity,
                          "version_count": len(versions), "version_label": versions[0]["label"],
                          "human_decision": next((d for d in workspace["decisions"] if d["version"] == versions[0]["number"]), None),
                          "previous_decision": workspace["decisions"][0] if workspace["decisions"] else None}
            seen.add(identity)
            rows.append(report)
        return rows


def compare_versions(workspace, report_dir, before, after):
    versions = {v["number"]: v for v in workspace["versions"]}
    if before not in versions or after not in versions:
        raise ValueError("Both versions must belong to this project")
    old, new = versions[before], versions[after]
    old_summary = load_report_detail(report_dir, old["report_id"])["summary"]
    new_summary = load_report_detail(report_dir, new["report_id"])["summary"]
    inputs = [{"field": key, "before": old["request"].get(key), "after": new["request"].get(key)}
              for key in sorted(set(old["request"]) | set(new["request"]))
              if old["request"].get(key) != new["request"].get(key)]
    metrics = []
    for field in ("budget", "total_exposure", "moderate_roi", "overall_risk_score", "confidence", "recommendation"):
        a, b = old_summary.get(field), new_summary.get(field)
        delta = round(b - a, 4) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
        metrics.append({"field": field, "before": a, "after": b, "delta": delta})
    return {"before": old["label"], "after": new["label"], "inputs": inputs, "metrics": metrics}
