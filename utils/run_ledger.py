"""Run ledger generation for analysis auditability."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import json

from config import (
    ANTHROPIC_INPUT_PRICE_PER_MILLION,
    ANTHROPIC_OUTPUT_PRICE_PER_MILLION,
    MODEL_NAME,
    RUNS_DIR,
)
from tools.tmdb_tools import tmdb_client


def estimate_anthropic_cost(usage_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate Anthropic cost from captured token usage."""
    totals = usage_summary.get("totals", {})
    billable_input_tokens = (
        totals.get("input_tokens", 0)
        + totals.get("cache_creation_input_tokens", 0)
    )
    output_tokens = totals.get("output_tokens", 0)
    input_cost = billable_input_tokens / 1_000_000 * ANTHROPIC_INPUT_PRICE_PER_MILLION
    output_cost = output_tokens / 1_000_000 * ANTHROPIC_OUTPUT_PRICE_PER_MILLION
    return {
        "currency": "USD",
        "estimated": True,
        "input_price_per_million": ANTHROPIC_INPUT_PRICE_PER_MILLION,
        "output_price_per_million": ANTHROPIC_OUTPUT_PRICE_PER_MILLION,
        "billable_input_tokens": billable_input_tokens,
        "output_tokens": output_tokens,
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(input_cost + output_cost, 6),
        "note": "Estimate only. Override prices with ANTHROPIC_INPUT_PRICE_PER_MILLION and ANTHROPIC_OUTPUT_PRICE_PER_MILLION.",
    }


def summarize_model_usage(results: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate model usage from master and subagent metadata."""
    usage = results.get("usage_summary", {})
    master = usage.get("master_orchestrator", {})
    subagents = usage.get("subagents", {})

    participants = {"master_orchestrator": master}
    participants.update(subagents)

    totals = {
        "call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    models = set()

    for summary in participants.values():
        totals["call_count"] += summary.get("call_count", 0)
        totals["input_tokens"] += summary.get("input_tokens", 0)
        totals["output_tokens"] += summary.get("output_tokens", 0)
        totals["cache_creation_input_tokens"] += summary.get("cache_creation_input_tokens", 0)
        totals["cache_read_input_tokens"] += summary.get("cache_read_input_tokens", 0)
        models.update(summary.get("models", []))

    return {
        "configured_model": MODEL_NAME,
        "models": sorted(models),
        "totals": totals,
        "participants": participants,
    }


def build_run_ledger(results: Dict[str, Any], report_path: Path) -> Dict[str, Any]:
    """Build a serializable run ledger for one analysis."""
    model_usage = summarize_model_usage(results)
    return {
        "schema_version": "1.0",
        "generated_at": datetime.utcnow().isoformat(),
        "project": results.get("requested_project_data", results.get("project_data", {})),
        "report_path": str(report_path),
        "recommendation": results.get("final_recommendation", {}).get("recommendation"),
        "confidence": results.get("final_recommendation", {}).get("confidence"),
        "model_usage": model_usage,
        "estimated_anthropic_cost": estimate_anthropic_cost(model_usage),
        "tmdb_usage": tmdb_client.get_usage_summary(),
    }


def save_run_ledger(results: Dict[str, Any], report_path: Path) -> Path:
    """Save the run ledger next to other generated run artifacts."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ledger = build_run_ledger(results, report_path)
    report_stem = Path(report_path).stem
    filepath = RUNS_DIR / f"{report_stem}_run.json"
    with open(filepath, "w") as f:
        json.dump(ledger, f, indent=2)
    return filepath
