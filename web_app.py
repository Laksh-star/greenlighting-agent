"""Local FastAPI demo UI for the greenlighting agent."""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import OUTPUT_DIR
from main import GreenlightingCLI, parse_comparables
from utils.sample_data import SAMPLE_PROJECT


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="Greenlighting Agent Demo")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

JOBS: Dict[str, Dict[str, Any]] = {}


class AnalysisRequest(BaseModel):
    description: str = Field(..., min_length=10)
    budget: int = Field(0, ge=0)
    genre: str = "Unknown"
    platform: str = Field("theatrical", pattern="^(theatrical|streaming|hybrid)$")
    comparables: str = ""
    target_audience: str = "general"
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


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    """Return current job state and result metadata."""
    job = _get_job(job_id)
    result = job.get("result") or {}
    return {
        "id": job_id,
        "status": job["status"],
        "error": job.get("error", ""),
        "events": job["events"],
        "recommendation": (result.get("final_recommendation") or {}).get("recommendation"),
        "confidence": (result.get("final_recommendation") or {}).get("confidence"),
        "report_path": result.get("report_path"),
        "analysis_json_path": result.get("analysis_json_path"),
        "download_markdown_url": f"/api/jobs/{job_id}/download/markdown" if result else "",
        "download_json_url": f"/api/jobs/{job_id}/download/json" if result else "",
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
        result = await cli.analyze_project(
            description=request.description,
            budget=request.budget,
            genre=request.genre,
            platform=request.platform,
            comparables=parse_comparables(request.comparables),
            target_audience=request.target_audience,
            demo_mode=request.demo_mode,
        )
        JOBS[job_id]["result"] = result
        JOBS[job_id]["status"] = "completed"
        _append_event(job_id, "job", "analysis", "completed")
    except Exception as exc:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(exc)
        _append_event(job_id, "job", "analysis", "failed", {"error": str(exc)})


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
    output_root = OUTPUT_DIR.resolve()
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
