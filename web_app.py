"""Local FastAPI demo UI for the greenlighting agent."""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import OUTPUT_DIR
from main import GreenlightingCLI, parse_comparables
from tools.tmdb_tools import tmdb_client
from tools.private_dataset import PRIVATE_DATASET_SAMPLE, private_dataset_store
from utils.batch import build_batch_summary_row, load_batch_projects_from_text, save_batch_summary
from utils.report_library import list_report_summaries, load_report_detail
from utils.sample_data import SAMPLE_PROJECT
from utils.slate_dashboard import build_slate_dashboard
from utils.source_material import build_source_material_payload
from utils.studio_brief import build_studio_brief, build_studio_brief_html


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="Greenlighting Agent Demo")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

JOBS: Dict[str, Dict[str, Any]] = {}

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w185"
FALLBACK_COMPARABLES = [
    {
        "id": "fallback-ex-machina",
        "title": "Ex Machina",
        "year": "2015",
        "rating": 7.6,
        "popularity": 41.2,
        "budget": 15_000_000,
        "revenue": 36_900_000,
        "poster_url": "",
        "overview": "Contained sci-fi thriller with AI themes and premium positioning.",
        "source": "demo fallback",
    },
    {
        "id": "fallback-moon",
        "title": "Moon",
        "year": "2009",
        "rating": 7.6,
        "popularity": 24.4,
        "budget": 5_000_000,
        "revenue": 9_800_000,
        "poster_url": "",
        "overview": "Contained lunar sci-fi drama with a modest production profile.",
        "source": "demo fallback",
    },
    {
        "id": "fallback-arrival",
        "title": "Arrival",
        "year": "2016",
        "rating": 7.6,
        "popularity": 51.6,
        "budget": 47_000_000,
        "revenue": 203_400_000,
        "poster_url": "",
        "overview": "Adult-skewing original sci-fi with strong critical and commercial upside.",
        "source": "demo fallback",
    },
    {
        "id": "fallback-paranormal-activity",
        "title": "Paranormal Activity",
        "year": "2007",
        "rating": 6.0,
        "popularity": 35.0,
        "budget": 15_000,
        "revenue": 193_000_000,
        "poster_url": "",
        "overview": "Micro-budget found footage horror with breakout theatrical ROI.",
        "source": "demo fallback",
    },
    {
        "id": "fallback-host",
        "title": "Host",
        "year": "2020",
        "rating": 6.5,
        "popularity": 18.0,
        "budget": 0,
        "revenue": 0,
        "poster_url": "",
        "overview": "Lean screenlife horror with a clear contained execution model.",
        "source": "demo fallback",
    },
]


class AnalysisRequest(BaseModel):
    description: str = Field(..., min_length=10)
    budget: int = Field(0, ge=0)
    genre: str = "Unknown"
    platform: str = Field("theatrical", pattern="^(theatrical|streaming|hybrid)$")
    comparables: str = ""
    target_audience: str = "general"
    demo_mode: bool = False
    comparable_source: str = Field("tmdb", pattern="^(tmdb|private|both)$")
    private_dataset_id: str = ""
    marketing_spend: int = Field(0, ge=0)
    distribution_fee_pct: float = Field(0.12, ge=0, le=0.5)
    theatrical_revenue_share: float = Field(0.5, ge=0, le=1)
    streaming_license_value: int = Field(0, ge=0)
    subscriber_lifetime_value: int = Field(120, ge=1)
    downside_revenue_multiplier: float = Field(0, ge=0)
    base_revenue_multiplier: float = Field(0, ge=0)
    upside_revenue_multiplier: float = Field(0, ge=0)
    risk_tolerance: str = Field("balanced", pattern="^(conservative|balanced|aggressive)$")
    source_material_name: str = ""
    source_material_text: str = ""


class BatchAnalysisRequest(BaseModel):
    csv_text: str = Field(..., min_length=20)
    demo_mode: bool = False


@app.get("/")
async def index():
    """Serve the local demo UI."""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/sample")
async def sample_project():
    """Return the deterministic no-key sample payload."""
    return {
        **SAMPLE_PROJECT,
        "comparables": ", ".join(SAMPLE_PROJECT.get("comparables", [])),
    }


@app.get("/api/sample-batch")
async def sample_batch():
    """Return a small no-key batch CSV sample."""
    sample_csv = (
        "description,budget,genre,platform,comparables,target_audience\n"
        "\"A contained sci-fi thriller about a lunar mining crew and a rogue AI\",18000000,"
        "Science Fiction,hybrid,\"Ex Machina,Moon,Arrival\",\"adults 18-49, sci-fi fans\"\n"
        "\"Found footage horror about investigators trapped in an abandoned hotel\",2500000,"
        "Horror,theatrical,\"Paranormal Activity,Host\",\"horror fans 18-34\"\n"
    )
    return {"csv_text": sample_csv}


@app.get("/api/private-datasets/sample")
async def private_dataset_sample():
    """Return a sample private dataset CSV."""
    return {"csv_text": PRIVATE_DATASET_SAMPLE}


@app.get("/api/private-datasets")
async def list_private_datasets():
    """List locally saved private datasets."""
    return {"datasets": private_dataset_store.list_datasets()}


class PrivateDatasetRequest(BaseModel):
    name: str = Field(..., min_length=1)
    csv_text: str = Field(..., min_length=20)


@app.post("/api/private-datasets")
async def save_private_dataset(request: PrivateDatasetRequest):
    """Save a private dataset locally."""
    metadata = private_dataset_store.save_dataset(request.name, request.csv_text)
    return {"dataset": metadata}


@app.get("/api/comparables/search")
async def search_comparables(
    q: str = Query(..., min_length=2),
    limit: int = Query(6, ge=1, le=10),
    source: str = Query("tmdb", pattern="^(tmdb|private|both)$"),
    dataset_id: str = "",
):
    """Search TMDB and/or private datasets for comparable title candidates."""
    return _search_comparable_sources(q, limit, source, dataset_id)


@app.post("/api/analyze")
async def analyze(request: AnalysisRequest):
    """Start an async analysis job and return its ID."""
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "id": job_id,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "events": [],
        "result": None,
        "error": "",
    }
    _append_event(job_id, "job", "analysis", "queued")
    asyncio.create_task(_run_analysis(job_id, request))
    return {"job_id": job_id, "events_url": f"/api/jobs/{job_id}/events"}


@app.post("/api/batch-analyze")
async def batch_analyze(request: BatchAnalysisRequest):
    """Start an async batch comparison job and return its ID."""
    projects = load_batch_projects_from_text(request.csv_text)
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "id": job_id,
        "kind": "batch",
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "events": [],
        "result": None,
        "error": "",
        "total_projects": len(projects),
    }
    _append_event(job_id, "job", "batch", "queued", {"total": len(projects)})
    asyncio.create_task(_run_batch_analysis(job_id, projects, request.demo_mode))
    return {"job_id": job_id, "events_url": f"/api/jobs/{job_id}/events"}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    """Return current job state and result metadata."""
    job = _get_job(job_id)
    result = job.get("result") or {}
    return {
        "id": job_id,
        "kind": job.get("kind", "single"),
        "status": job["status"],
        "error": job.get("error", ""),
        "events": job["events"],
        "total_projects": job.get("total_projects"),
        "recommendation": (result.get("final_recommendation") or {}).get("recommendation"),
        "confidence": (result.get("final_recommendation") or {}).get("confidence"),
        "report_path": result.get("report_path"),
        "analysis_json_path": result.get("analysis_json_path"),
        "rows": result.get("rows", []),
        "csv_path": result.get("csv_path", ""),
        "json_path": result.get("json_path", ""),
        "download_batch_csv_url": f"/api/jobs/{job_id}/download/batch-csv" if result.get("csv_path") else "",
        "download_batch_json_url": f"/api/jobs/{job_id}/download/batch-json" if result.get("json_path") else "",
        "download_markdown_url": f"/api/jobs/{job_id}/download/markdown"
        if result.get("report_path")
        else "",
        "download_json_url": f"/api/jobs/{job_id}/download/json"
        if result.get("analysis_json_path")
        else "",
    }


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    """Stream job progress as Server-Sent Events."""
    _get_job(job_id)

    async def event_stream():
        seen = 0
        while True:
            job = _get_job(job_id)
            while seen < len(job["events"]):
                payload = json.dumps(job["events"][seen])
                yield f"data: {payload}\n\n"
                seen += 1
            if job["status"] in {"completed", "failed"}:
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/report")
async def report_markdown(job_id: str):
    """Return generated Markdown for preview rendering."""
    job = _get_completed_job(job_id)
    report_path = Path(job["result"]["report_path"])
    return PlainTextResponse(_read_output_file(report_path, ".md"))


@app.get("/api/jobs/{job_id}/download/markdown")
async def download_markdown(job_id: str):
    """Download generated Markdown report."""
    job = _get_completed_job(job_id)
    return _download_output_file(Path(job["result"]["report_path"]), "text/markdown")


@app.get("/api/jobs/{job_id}/download/json")
async def download_json(job_id: str):
    """Download generated structured JSON report."""
    job = _get_completed_job(job_id)
    return _download_output_file(Path(job["result"]["analysis_json_path"]), "application/json")


@app.get("/api/jobs/{job_id}/download/batch-csv")
async def download_batch_csv(job_id: str):
    """Download generated batch CSV summary."""
    job = _get_completed_job(job_id)
    return _download_output_file(Path(job["result"]["csv_path"]), "text/csv")


@app.get("/api/jobs/{job_id}/download/batch-json")
async def download_batch_json(job_id: str):
    """Download generated batch JSON summary."""
    job = _get_completed_job(job_id)
    return _download_output_file(Path(job["result"]["json_path"]), "application/json")


@app.get("/api/output")
async def output_file(path: str = Query(...)):
    """Download a generated output file by safe relative path."""
    output_path = Path(path)
    media_type = {
        ".md": "text/markdown",
        ".json": "application/json",
        ".csv": "text/csv",
    }.get(output_path.suffix, "text/plain")
    return _download_output_file(output_path, media_type)


@app.get("/api/reports")
async def report_library(limit: int = Query(25, ge=1, le=100)):
    """List generated local reports."""
    return {"reports": list_report_summaries(OUTPUT_DIR, limit=limit)}


@app.get("/api/slate-dashboard")
async def slate_dashboard(limit: int = Query(50, ge=1, le=100)):
    """Return slate-level metrics from saved local reports."""
    reports = list_report_summaries(OUTPUT_DIR, limit=limit)
    return build_slate_dashboard(reports)


@app.get("/api/reports/{report_id}")
async def report_detail(report_id: str):
    """Return one generated report with Markdown preview content."""
    try:
        return load_report_detail(OUTPUT_DIR, report_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Report not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid report id")


@app.get("/api/reports/{report_id}/brief")
async def report_brief(report_id: str):
    """Return a compact studio brief generated from one saved report."""
    try:
        detail = load_report_detail(OUTPUT_DIR, report_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Report not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid report id")
    filename = f"{report_id}_brief.md"
    return PlainTextResponse(
        build_studio_brief(detail["payload"]),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/reports/{report_id}/brief-print")
async def report_brief_print(report_id: str):
    """Return a printable studio brief HTML page."""
    try:
        detail = load_report_detail(OUTPUT_DIR, report_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Report not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid report id")
    return HTMLResponse(build_studio_brief_html(detail["payload"]))


async def _run_analysis(job_id: str, request: AnalysisRequest):
    JOBS[job_id]["status"] = "running"
    _append_event(job_id, "job", "analysis", "started")

    async def progress_callback(event: Dict[str, Any]):
        _append_event(
            job_id,
            event.get("stage", "agent"),
            event.get("name", ""),
            event.get("status", ""),
            {
                key: value
                for key, value in event.items()
                if key not in {"stage", "name", "status"}
            },
        )

    cli = GreenlightingCLI(progress_callback=progress_callback)

    try:
        comparable_titles = parse_comparables(request.comparables)
        source_material = None
        if request.source_material_text.strip():
            source_material = build_source_material_payload(
                request.source_material_text,
                name=request.source_material_name or "uploaded source material",
            )
        comparable_evidence, market_data_warning = _build_private_comparable_evidence(
            comparable_titles,
            request.comparable_source,
            request.private_dataset_id,
        )
        result = await cli.analyze_project(
            description=request.description,
            budget=request.budget,
            genre=request.genre,
            platform=request.platform,
            comparables=comparable_titles,
            target_audience=request.target_audience,
            demo_mode=request.demo_mode,
            comparable_evidence=comparable_evidence,
            market_data_warning=market_data_warning,
            comparable_source=request.comparable_source,
            private_dataset_id=request.private_dataset_id,
            financial_assumptions={
                "marketing_spend": request.marketing_spend,
                "distribution_fee_pct": request.distribution_fee_pct,
                "theatrical_revenue_share": request.theatrical_revenue_share,
                "streaming_license_value": request.streaming_license_value,
                "subscriber_lifetime_value": request.subscriber_lifetime_value,
                "downside_revenue_multiplier": request.downside_revenue_multiplier,
                "base_revenue_multiplier": request.base_revenue_multiplier,
                "upside_revenue_multiplier": request.upside_revenue_multiplier,
                "risk_tolerance": request.risk_tolerance,
            },
            source_material=source_material,
        )
        JOBS[job_id]["result"] = result
        JOBS[job_id]["status"] = "completed"
        _append_event(job_id, "job", "analysis", "completed")
    except Exception as exc:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(exc)
        _append_event(job_id, "job", "analysis", "failed", {"error": str(exc)})


async def _run_batch_analysis(job_id: str, projects: list, demo_mode: bool):
    JOBS[job_id]["status"] = "running"
    _append_event(job_id, "job", "batch", "started", {"total": len(projects)})
    rows = []
    results = []

    try:
        for index, project in enumerate(projects, start=1):
            _append_event(
                job_id,
                "batch_project",
                f"Project {index}",
                "started",
                {"completed": index - 1, "total": len(projects)},
            )
            cli = GreenlightingCLI(
                progress_callback=_make_batch_progress_callback(job_id, index, len(projects))
            )
            result = await cli.analyze_project(
                **project,
                demo_mode=demo_mode,
            )
            rows.append(build_batch_summary_row(result))
            results.append(result)
            _append_event(
                job_id,
                "batch_project",
                f"Project {index}",
                "completed",
                {"completed": index, "total": len(projects)},
            )

        summary_paths = save_batch_summary(rows)
        JOBS[job_id]["result"] = {
            "rows": rows,
            "project_results": results,
            **summary_paths,
        }
        JOBS[job_id]["status"] = "completed"
        _append_event(job_id, "job", "batch", "completed", {"total": len(projects)})
    except Exception as exc:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(exc)
        _append_event(job_id, "job", "batch", "failed", {"error": str(exc)})


def _make_batch_progress_callback(job_id: str, project_index: int, project_total: int):
    async def progress_callback(event: Dict[str, Any]):
        _append_event(
            job_id,
            event.get("stage", "agent"),
            f"P{project_index}: {event.get('name', '')}",
            event.get("status", ""),
            {
                "project_index": project_index,
                "project_total": project_total,
                **{
                    key: value
                    for key, value in event.items()
                    if key not in {"stage", "name", "status"}
                },
            },
        )

    return progress_callback


def _search_comparable_sources(query: str, limit: int, source: str, dataset_id: str) -> Dict[str, Any]:
    results = []
    warnings = []
    sources = []

    if source in ("private", "both"):
        private_rows = private_dataset_store.search(query, dataset_id=dataset_id, limit=limit)
        if private_rows:
            results.extend(private_rows)
            sources.append("private dataset")
        elif source == "private":
            warnings.append("No private dataset matches found.")

    if source in ("tmdb", "both") and len(results) < limit:
        try:
            tmdb_rows = _search_tmdb_comparables(query, limit - len(results))
            if tmdb_rows:
                results.extend(tmdb_rows)
                sources.append("tmdb")
        except Exception as exc:
            warnings.append(f"TMDB search unavailable: {exc}")

    if not results:
        results = _fallback_comparable_search(query, limit)
        sources.append("demo fallback")

    return {
        "results": results[:limit],
        "source": " + ".join(dict.fromkeys(sources)),
        "warning": " ".join(warnings),
    }


def _search_tmdb_comparables(query: str, limit: int) -> list:
    matches = tmdb_client.search_movie(query)[:limit]
    results = []
    for match in matches:
        details = {}
        movie_id = match.get("id")
        if movie_id:
            try:
                details = tmdb_client.get_movie_details(movie_id)
            except Exception:
                details = {}
        results.append(_format_comparable_search_result(match, details))
    return results


def _build_private_comparable_evidence(
    comparable_titles: list,
    comparable_source: str,
    dataset_id: str,
) -> tuple:
    if comparable_source not in ("private", "both") or not comparable_titles:
        return None, ""

    private_evidence = private_dataset_store.comparable_evidence_for_titles(
        comparable_titles,
        dataset_id=dataset_id,
    )
    found_titles = {item["title"].lower() for item in private_evidence}
    missing = [
        title
        for title in comparable_titles
        if title.lower() not in found_titles
    ]

    warning = ""
    if missing and comparable_source == "private":
        warning = (
            "Private dataset missing comparable rows for: "
            + ", ".join(missing)
        )
        private_evidence.extend(_fallback_private_rows(missing))

    if comparable_source == "both" and missing:
        try:
            private_evidence.extend(tmdb_client.enrich_comparable_titles(missing))
        except Exception as exc:
            warning = f"TMDB enrichment unavailable for private+TMDB mode: {exc}"
            private_evidence.extend(_fallback_private_rows(missing))

    return private_evidence if private_evidence else None, warning


def _fallback_private_rows(titles: list) -> list:
    return [
        {
            "title": title,
            "year": "n/a",
            "budget": 0,
            "revenue": 0,
            "roi": 0.0,
            "rating": 0,
            "popularity": 0,
            "similar_titles": [],
            "source": "private dataset missing",
        }
        for title in titles
    ]


def _format_comparable_search_result(match: Dict[str, Any], details: Dict[str, Any]) -> Dict[str, Any]:
    poster_path = details.get("poster_path") or match.get("poster_path") or ""
    release_date = details.get("release_date") or match.get("release_date") or ""
    return {
        "id": match.get("id"),
        "title": details.get("title") or match.get("title") or "Untitled",
        "year": release_date[:4] or "n/a",
        "rating": details.get("vote_average", match.get("vote_average", 0)) or 0,
        "popularity": details.get("popularity", match.get("popularity", 0)) or 0,
        "budget": details.get("budget", 0) or 0,
        "revenue": details.get("revenue", 0) or 0,
        "poster_url": f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else "",
        "overview": details.get("overview") or match.get("overview") or "",
        "source": "tmdb",
    }


def _fallback_comparable_search(query: str, limit: int) -> list:
    normalized = query.lower().strip()
    matches = [
        item
        for item in FALLBACK_COMPARABLES
        if normalized in item["title"].lower() or normalized in item["overview"].lower()
    ]
    return (matches or FALLBACK_COMPARABLES)[:limit]


def _append_event(
    job_id: str,
    stage: str,
    name: str,
    status: str,
    extra: Dict[str, Any] = None,
):
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "stage": stage,
        "name": name,
        "status": status,
    }
    if extra:
        event.update(extra)
    JOBS[job_id]["events"].append(event)


def _get_job(job_id: str) -> Dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _get_completed_job(job_id: str) -> Dict[str, Any]:
    job = _get_job(job_id)
    if job["status"] != "completed" or not job.get("result"):
        raise HTTPException(status_code=409, detail="Job is not complete")
    return job


def _read_output_file(path: Path, suffix: str) -> str:
    resolved = _validated_output_path(path, suffix)
    return resolved.read_text()


def _download_output_file(path: Path, media_type: str):
    resolved = _validated_output_path(path, path.suffix)
    return FileResponse(
        resolved,
        media_type=media_type,
        filename=resolved.name,
    )


def _validated_output_path(path: Path, suffix: str) -> Path:
    resolved = (BASE_DIR / path).resolve() if not path.is_absolute() else path.resolve()
    output_root = OUTPUT_DIR.parent.resolve()
    if suffix and resolved.suffix != suffix:
        raise HTTPException(status_code=400, detail="Unexpected file type")
    if output_root not in resolved.parents:
        raise HTTPException(status_code=400, detail="Invalid output path")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    return resolved


@app.exception_handler(Exception)
async def unhandled_exception_handler(_, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})
