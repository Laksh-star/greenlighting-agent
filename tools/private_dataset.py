"""Local private dataset support for studio-specific comparable evidence."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from config import PRIVATE_DATA_DIR
from utils.helpers import sanitize_filename


PRIVATE_DATASET_COLUMNS = [
    "title",
    "year",
    "genre",
    "platform",
    "budget",
    "marketing_spend",
    "revenue",
    "rating",
    "popularity",
    "audience",
    "territory",
    "notes",
]

PRIVATE_DATASET_SAMPLE = """title,year,genre,platform,budget,marketing_spend,revenue,rating,popularity,audience,territory,notes
Lunar Signal,2019,Science Fiction,hybrid,12000000,8000000,42000000,7.4,34.2,"adults 18-49","US/UK","Contained sci-fi thriller with strong streamer tail"
Hotel Haunt,2021,Horror,theatrical,1800000,3000000,28000000,6.3,22.1,"horror fans 18-34","Domestic","Low-budget contained horror with efficient P&A"
City Witness,2020,Drama,streaming,9000000,1500000,0,7.1,18.8,"adults 25-54","Global","Prestige drama used for subscriber retention"
"""


class PrivateDatasetStore:
    """Persist and search private comparable datasets on local disk."""

    def __init__(self, base_dir: Path = PRIVATE_DATA_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_dataset(self, name: str, csv_text: str) -> Dict[str, Any]:
        dataset_id = sanitize_filename(name.strip() or "private_dataset").lower()
        if not dataset_id:
            dataset_id = "private_dataset"
        rows = parse_private_dataset_csv(csv_text)
        csv_path = self.base_dir / f"{dataset_id}.csv"
        metadata_path = self.base_dir / f"{dataset_id}.json"
        csv_path.write_text(csv_text)
        metadata = {
            "id": dataset_id,
            "name": name.strip() or dataset_id,
            "row_count": len(rows),
            "created_at": datetime.utcnow().isoformat(),
            "csv_path": str(csv_path),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2))
        return metadata

    def list_datasets(self) -> List[Dict[str, Any]]:
        datasets = []
        for metadata_path in sorted(self.base_dir.glob("*.json")):
            try:
                datasets.append(json.loads(metadata_path.read_text()))
            except json.JSONDecodeError:
                continue
        return datasets

    def load_dataset(self, dataset_id: str) -> List[Dict[str, Any]]:
        csv_path = self._dataset_csv_path(dataset_id)
        if not csv_path.exists():
            return []
        return parse_private_dataset_csv(csv_path.read_text())

    def search(self, query: str, dataset_id: str = "", limit: int = 8) -> List[Dict[str, Any]]:
        rows = self._search_rows(dataset_id)
        normalized = query.lower().strip()
        scored = []
        for row in rows:
            haystack = " ".join([
                str(row.get("title", "")),
                str(row.get("genre", "")),
                str(row.get("platform", "")),
                str(row.get("audience", "")),
                str(row.get("notes", "")),
            ]).lower()
            if normalized in haystack:
                score = 2 if normalized in str(row.get("title", "")).lower() else 1
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored[:limit]]

    def comparable_evidence_for_titles(
        self,
        titles: List[str],
        dataset_id: str = "",
    ) -> List[Dict[str, Any]]:
        rows = self._search_rows(dataset_id)
        by_title = {row["title"].lower(): row for row in rows}
        evidence = []
        for title in titles:
            row = by_title.get(title.lower())
            if row:
                evidence.append(row)
        return evidence

    def _search_rows(self, dataset_id: str = "") -> List[Dict[str, Any]]:
        if dataset_id:
            return self.load_dataset(dataset_id)
        rows = []
        for csv_path in sorted(self.base_dir.glob("*.csv")):
            rows.extend(parse_private_dataset_csv(csv_path.read_text()))
        return rows

    def _dataset_csv_path(self, dataset_id: str) -> Path:
        return self.base_dir / f"{sanitize_filename(dataset_id).lower()}.csv"


def parse_private_dataset_csv(csv_text: str) -> List[Dict[str, Any]]:
    """Normalize private dataset CSV rows into comparable evidence rows."""
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    for index, row in enumerate(reader, start=1):
        title = (row.get("title") or row.get("name") or "").strip()
        if not title:
            raise ValueError(f"Private dataset row {index} is missing title")
        budget = parse_int(row.get("budget"))
        revenue = parse_int(row.get("revenue") or row.get("box_office"))
        rows.append({
            "id": f"private-{sanitize_filename(title).lower()}-{index}",
            "title": title,
            "year": str(row.get("year") or "n/a").strip() or "n/a",
            "genre": (row.get("genre") or "").strip(),
            "platform": (row.get("platform") or "").strip(),
            "budget": budget,
            "marketing_spend": parse_int(row.get("marketing_spend") or row.get("p_and_a")),
            "revenue": revenue,
            "roi": calculate_roi(budget, revenue),
            "rating": parse_float(row.get("rating")),
            "popularity": parse_float(row.get("popularity")),
            "audience": (row.get("audience") or row.get("target_audience") or "").strip(),
            "territory": (row.get("territory") or "").strip(),
            "notes": (row.get("notes") or "").strip(),
            "poster_url": "",
            "overview": (row.get("notes") or "").strip(),
            "similar_titles": [],
            "source": "private dataset",
        })
    return rows


def parse_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(str(value).replace(",", "").replace("$", "").strip()))
    except ValueError:
        return default


def parse_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return default


def calculate_roi(budget: int, revenue: int) -> float:
    if budget <= 0:
        return 0.0
    return round(((revenue - budget) / budget) * 100, 2)


private_dataset_store = PrivateDatasetStore()
