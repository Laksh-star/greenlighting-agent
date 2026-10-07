"""Conservative evidence labels: never invent retrieval dates or narrative citations."""


def build_provenance(payload):
    project = payload.get("project", {})
    demo = bool(project.get("demo_mode"))
    evidence = [{"id": "project-input", "source": "user input", "description": "Project description, budget, audience and treatment", "retrieved_at": None, "url": ""}]
    warnings = []
    rows = payload.get("comparable_evidence", [])
    for index, row in enumerate(rows, 1):
        source = row.get("source", "unknown legacy source")
        if demo and source not in ("private dataset", "input only"):
            source = "demo data"
        missing = [key for key in ("budget", "revenue") if not row.get(key)]
        evidence.append({"id": f"comparable-{index}", "source": source,
                         "description": row.get("title", "Unknown comparable"),
                         "retrieved_at": row.get("retrieved_at"), "url": row.get("source_url", ""),
                         "dataset_id": row.get("dataset_id", project.get("private_dataset_id", "")) if source == "private dataset" else "",
                         "missing_fields": missing})
        if missing:
            warnings.append(f"{row.get('title', 'Comparable')}: missing or unreported {', '.join(missing)}.")
        if source in ("input only", "unknown legacy source"):
            warnings.append(f"{row.get('title', 'Comparable')}: financial evidence is not source-verified.")
    if project.get("comparables") and not rows:
        warnings.append("Comparable titles supplied but no enrichment evidence retained.")
    evidence.extend([
        {"id": "financial-model", "source": "deterministic model", "description": "Financial scenarios derived from assumptions and comparable signals", "retrieved_at": None, "url": ""},
        {"id": "financial-assumptions", "source": "user assumption / model default", "description": "Normalized financial assumptions; supplied values may be UI defaults, and editing intent is not recorded", "retrieved_at": None, "url": ""},
        {"id": "risk-model", "source": "deterministic heuristic", "description": "Budget, genre and platform risk score; not empirical loss probability", "retrieved_at": None, "url": ""},
        {"id": "narrative", "source": "demo narrative" if demo else "AI interpretation", "description": "Narrative assessment and final synthesis; not independent market evidence", "retrieved_at": None, "url": ""},
    ])
    requested = project.get("financial_assumptions") or {}
    for name, value in payload.get("financial_assumptions", {}).items():
        evidence.append({"id": f"assumption-{name}",
                         "source": "model default (zero sentinel)" if name.endswith("_revenue_multiplier") and value == 0 else "user assumption" if requested.get(name) is not None else "model default",
                         "description": f"{name}: {value}", "effective_value": value,
                         "requested_value": requested.get(name), "retrieved_at": None, "url": ""})
    finance = payload.get("financial_scenarios", {})
    risk = payload.get("risk_matrix", {})
    supported = {f"Comparable evidence rows reviewed: {len(rows)}.": "comparable-count"}
    if finance.get("moderate_roi") is not None:
        supported[f"Moderate-case ROI: {finance['moderate_roi']}%."] = "financial-model"
    if risk.get("risk_level"):
        supported[f"Risk profile: {risk['risk_level']}."] = "risk-model"
    evidence.append({"id": "comparable-count", "source": "retained evidence count", "description": f"{len(rows)} comparable rows; count is not evidence quality", "retrieved_at": None, "url": ""})
    drivers = [{"text": text, "status": "linked calculation" if text in supported else "unsupported interpretation",
                "evidence_ids": [supported[text]] if text in supported else []} for text in payload.get("decision_drivers", [])]
    warning = payload.get("subagent_results", {}).get("market_research", {}).get("metadata", {}).get("market_data_warning")
    if warning:
        warnings.append(warning)
    if demo:
        warnings.append("Demo mode: narratives are simulated, not live AI research. Comparable sources are labelled individually.")
    return {"schema_version": "1.0", "evidence": evidence, "decision_drivers": drivers,
            "warnings": warnings, "note": "Links cover exact retained calculations only; narrative claims without evidence links are not independently verified."}


def provenance_from_results(results):
    agents = results.get("subagent_results", {})
    metadata = lambda name: agents.get(name, {}).get("metadata", {})
    return build_provenance({
        "project": results.get("requested_project_data", results.get("project_data", {})),
        "comparable_evidence": metadata("market_research").get("comparable_evidence", []),
        "financial_scenarios": metadata("financial_model").get("basic_metrics", {}),
        "financial_assumptions": metadata("financial_model").get("assumptions", {}),
        "risk_matrix": metadata("risk_analysis"),
        "decision_drivers": results.get("final_recommendation", {}).get("decision_drivers", []),
        "subagent_results": agents,
    })
