// Studio Lot: a strategy-game style view of the greenlight slate.
// Reads the same local API as the classic view; nothing here changes the agents.

import { createLot } from "/static/lot-scene.js";

const AGENTS = [
  { key: "market_research", short: "Market", name: "Market research" },
  { key: "audience_intel", short: "Audience", name: "Audience intelligence" },
  { key: "financial_model", short: "Finance", name: "Financial modeling" },
  { key: "competitive", short: "Competitive", name: "Competitive analysis" },
  { key: "creative", short: "Creative", name: "Creative assessment" },
  { key: "risk_analysis", short: "Risk", name: "Risk analysis" },
];
// Market research runs first; every other agent runs in the parallel step.
const PARALLEL_AGENTS = AGENTS.length - 1;
const MAX_STAGES = 12;
const REPORT_LIMIT = 100;
const EVENT_PACING_MS = 520;

const $ = (selector) => document.querySelector(selector);
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

const state = {
  reports: [],
  dashboard: null,
  totalReports: 0,
  isSample: false,
  selectedId: null,
  tab: "slate",
  details: new Map(),
  agentStates: Object.fromEntries(AGENTS.map((agent) => [agent.key, "idle"])),
  run: null,
};

// ---------- formatting ----------

function money(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "n/a";
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(n >= 1e8 ? 0 : 1)}M`;
  if (Math.abs(n) >= 1e3) return `$${Math.round(n / 1e3)}K`;
  return `$${Math.round(n)}`;
}

function percent(value, digits = 0) {
  const n = Number(value);
  if (value === "" || value === null || value === undefined || !Number.isFinite(n)) return "n/a";
  return `${n > 0 ? "+" : ""}${n.toFixed(digits)}%`;
}

function verdictKey(recommendation) {
  const text = String(recommendation || "").toUpperCase();
  if (text === "GO") return "go";
  if (text === "CONDITIONAL GO") return "cond";
  if (text === "NO-GO") return "nogo";
  return "unknown";
}

function badge(recommendation) {
  const key = verdictKey(recommendation);
  return `<span class="badge" data-v="${key === "unknown" ? "idle" : key}">${esc(recommendation || "Unrated")}</span>`;
}

function riskTone(score) {
  const n = Number(score);
  if (!Number.isFinite(n)) return "idle";
  if (n >= 6.5) return "nogo";
  if (n >= 4.5) return "cond";
  return "go";
}

function roiTone(roi) {
  const n = Number(roi);
  if (!Number.isFinite(n)) return "idle";
  if (n >= 35) return "go";
  if (n >= 0) return "cond";
  return "nogo";
}

function when(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

const slotLabel = (slot) => String(slot + 1).padStart(2, "0");

// ---------- sample slate (shown only while no reports exist) ----------

function sampleReport(index, spec) {
  const [name, description, genre, platform, audience, budget, recommendation, confidence, rois, risk, riskLevel, agentConfidence, drivers] = spec;
  const exposure = Math.round(budget * 1.5);
  const cases = ["Conservative", "Base", "Aggressive"].map((label, i) => ({
    case: label,
    base_roi: rois[i],
    base_gross_revenue: Math.round((exposure * (1 + rois[i] / 100)) / 0.440),
    total_exposure: exposure,
  }));
  const id = `sample-${index + 1}`;
  const summary = {
    id,
    generated_at: new Date(Date.now() - (6 - index) * 36e5).toISOString(),
    project_name: name,
    description,
    budget,
    genre,
    platform,
    target_audience: audience,
    recommendation,
    confidence,
    moderate_roi: rois[1],
    total_exposure: exposure,
    risk_level: riskLevel,
    overall_risk_score: risk,
    is_sample: true,
  };
  const payload = {
    project: { description },
    decision_drivers: drivers,
    scenario_comparison: cases,
    subagent_results: Object.fromEntries(AGENTS.map((agent, i) => [agent.key, { confidence: agentConfidence[i] }])),
  };
  return { summary, payload };
}

const SAMPLE_SLATE = [
  ["Lunar Ledger", "A contained sci-fi thriller about a lunar mining crew that finds its AI rewriting mission records.", "Science Fiction", "hybrid", "adults 18-49, sci-fi thriller fans", 18e6, "CONDITIONAL GO", 0.840, [-22, 14, 61], 5.2, "Medium Risk", [0.880, 0.820, 0.860, 0.780, 0.8, 0.9], ["Comparable contained sci-fi supports the upside case.", "Base-case return is positive but thin.", "Hold the budget and lock a streaming window."]],
  ["Room 414", "Found-footage horror about investigators trapped overnight in an abandoned hotel.", "Horror", "theatrical", "horror fans 18-34", 2.5e6, "GO", 0.910, [18, 96, 240], 3.1, "Low Risk", [0.920, 0.9, 0.930, 0.840, 0.860, 0.910], ["Micro-budget horror has the strongest return profile on the slate.", "Clear, reachable core audience.", "Downside case still clears break-even."]],
  ["The Long Table", "An ensemble family drama set across one wedding weekend in Hyderabad.", "Drama", "streaming", "adults 25-54, family audiences", 6e6, "GO", 0.870, [6, 48, 105], 3.8, "Low-Medium Risk", [0.850, 0.9, 0.880, 0.820, 0.910, 0.860], ["Streaming licence value covers most of the exposure.", "Strong creative package with a festival path.", "Low execution complexity."]],
  ["Iron Monsoon", "A period war epic following a railway battalion through the 1944 monsoon campaign.", "War", "theatrical", "adults 25+, history audiences", 95e6, "NO-GO", 0.790, [-58, -24, 22], 7.9, "High Risk", [0.810, 0.7, 0.840, 0.760, 0.740, 0.880], ["Capital at risk is out of proportion to comparable returns.", "Base case loses money at this budget.", "Revisit at a materially lower budget."]],
  ["Paper Kites", "An animated adventure about two siblings chasing a runaway kite across a city.", "Animation", "hybrid", "families, kids 6-12", 42e6, "CONDITIONAL GO", 0.760, [-31, 9, 74], 5.9, "Medium Risk", [0.8, 0.860, 0.780, 0.720, 0.830, 0.790], ["Family audience demand is proven, but the release window is crowded.", "Needs a co-financing partner to cap exposure.", "Merchandising upside is not in the base case."]],
  ["Second Unit", "A workplace comedy about the crew that shoots everything the stars will not.", "Comedy", "streaming", "adults 18-39, comedy fans", 9e6, "CONDITIONAL GO", 0.810, [-12, 21, 58], 4.6, "Low-Medium Risk", [0.830, 0.840, 0.820, 0.790, 0.870, 0.850], ["Comedy travels less well internationally.", "Series potential improves lifetime value.", "Attach a lead before greenlight."]],
].map((spec, index) => sampleReport(index, spec));

function localDashboard(reports) {
  const counts = { GO: 0, "CONDITIONAL GO": 0, "NO-GO": 0, UNKNOWN: 0 };
  let exposure = 0;
  let budget = 0;
  const rois = [];
  for (const report of reports) {
    const key = { go: "GO", cond: "CONDITIONAL GO", nogo: "NO-GO" }[verdictKey(report.recommendation)] || "UNKNOWN";
    counts[key] += 1;
    exposure += Number(report.total_exposure) || 0;
    budget += Number(report.budget) || 0;
    if (Number.isFinite(Number(report.moderate_roi))) rois.push(Number(report.moderate_roi));
  }
  return {
    report_count: reports.length,
    recommendation_counts: counts,
    total_budget: budget,
    total_exposure: exposure,
    average_roi: rois.length ? rois.reduce((a, b) => a + b, 0) / rois.length : 0,
    watchlist: [...reports].sort((a, b) => Number(b.overall_risk_score) - Number(a.overall_risk_score)).slice(0, 5),
  };
}

// ---------- scene ----------

const lot = createLot($("#scene"), AGENTS, {
  onPick(target) {
    if (target.kind === "stage") selectProject(target.id);
    if (target.kind === "vacant" || target.kind === "office") openPitch();
    if (target.kind === "agent") setTab("agents");
  },
  onHover(target, x, y) {
    const tip = $("#tooltip");
    if (!target) {
      tip.hidden = true;
      return;
    }
    let html = "";
    if (target.kind === "stage") {
      const report = state.reports.find((item) => item.id === target.id);
      if (!report) return;
      html = `Stage ${slotLabel(report.slot)} · ${esc(report.project_name)}<small>${esc(report.recommendation || "Unrated")} · ${money(report.budget)} budget</small>`;
    } else if (target.kind === "vacant") {
      html = `Vacant pad · Stage ${slotLabel(target.slot)}<small>Click to pitch a project</small>`;
    } else if (target.kind === "office") {
      html = "Greenlight Office<small>Master orchestrator · click to pitch a project</small>";
    } else if (target.kind === "agent") {
      const agent = AGENTS.find((item) => item.key === target.id);
      html = `${esc(agent.name)} agent<small>${esc(agentStatusText(agent.key))}</small>`;
    }
    tip.innerHTML = html;
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
    tip.hidden = false;
  },
});

function syncInsets() {
  const desktop = window.matchMedia("(min-width: 981px)").matches;
  if (!desktop) {
    lot.setInsets({ top: 0, right: 0, bottom: 0, left: 0 });
    return;
  }
  const detail = $("#detail").getBoundingClientRect();
  const tracker = $("#tracker").getBoundingClientRect();
  const kpis = document.querySelector(".kpis").getBoundingClientRect();
  lot.setInsets({
    top: kpis.bottom - 6,
    right: window.innerWidth - detail.left + 62,
    bottom: window.innerHeight - tracker.top + 8,
    left: 0,
  });
}
window.addEventListener("resize", syncInsets);

document.querySelector(".mapctl").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-ctl]");
  if (button) lot.control(button.dataset.ctl);
});

// ---------- data ----------

async function getJSON(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail || detail;
    } catch {
      /* keep status text */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json();
}

async function loadSlate({ selectNewest = false } = {}) {
  let reports = [];
  let dashboard = null;
  try {
    const [library, slate] = await Promise.all([getJSON(`/api/reports?limit=${REPORT_LIMIT}`), getJSON(`/api/slate-dashboard?limit=${REPORT_LIMIT}`)]);
    reports = library.reports || [];
    dashboard = slate;
  } catch (error) {
    toast(`Could not load the slate: ${error.message}`);
  }

  state.isSample = reports.length === 0;
  if (state.isSample) {
    reports = SAMPLE_SLATE.map((item) => item.summary).reverse();
    dashboard = localDashboard(reports);
    for (const item of SAMPLE_SLATE) state.details.set(item.summary.id, item.payload);
  }

  state.totalReports = reports.length;
  // API order is newest first; stage numbers follow age so they stay put as the slate grows.
  state.reports = reports
    .slice(0, MAX_STAGES)
    .reverse()
    .map((report, slot) => ({ ...report, slot }));
  state.dashboard = dashboard;

  lot.setProjects(
    state.reports.map((report) => ({
      id: report.id,
      slot: report.slot,
      slotLabel: slotLabel(report.slot),
      verdict: verdictKey(report.recommendation),
      budget: report.budget,
    }))
  );

  renderKpis();
  const stillThere = state.reports.some((report) => report.id === state.selectedId);
  const newest = state.reports.at(-1);
  if (selectNewest && newest) selectProject(newest.id);
  else if (!stillThere && state.reports.length) selectProject(defaultSelection().id);
  else selectProject(state.selectedId);
  renderRoster();
}

function defaultSelection() {
  const top = state.dashboard?.top_projects?.[0];
  return state.reports.find((report) => report.id === top?.id) || state.reports.at(-1);
}

async function loadDetail(id) {
  if (state.details.has(id)) return state.details.get(id);
  const detail = await getJSON(`/api/reports/${encodeURIComponent(id)}`);
  state.details.set(id, detail.payload);
  return detail.payload;
}

// ---------- KPI cards ----------

function renderKpis() {
  const d = state.dashboard || {};
  const counts = d.recommendation_counts || {};
  // The page asks the API for at most 100 reports, so 100 is a floor, not a count.
  const count = d.report_count ?? 0;
  $("#kpi-projects").textContent = !state.isSample && count >= REPORT_LIMIT ? `${REPORT_LIMIT}+` : String(count);
  $("#kpi-projects-sub").textContent = `${counts.GO || 0} go · ${counts["CONDITIONAL GO"] || 0} conditional · ${counts["NO-GO"] || 0} no-go`;
  $("#kpi-exposure").textContent = money(d.total_exposure);
  $("#kpi-exposure-sub").textContent = `${money(d.total_budget)} production budgets`;
  $("#kpi-roi").textContent = d.report_count ? percent(d.average_roi, 1) : "n/a";
  $("#kpi-roi-sub").textContent = "moderate case, across the slate";
  const shown = state.reports.length;
  const chip = $("#slate-chip");
  if (state.isSample) chip.textContent = "Sample slate · no saved reports yet";
  else if (state.totalReports > shown) chip.textContent = `Lot shows the newest ${shown} of ${state.totalReports >= REPORT_LIMIT ? `${REPORT_LIMIT}+` : state.totalReports} reports`;
  else chip.textContent = `${shown} saved ${shown === 1 ? "report" : "reports"}`;
  $("#tab-slate-n").textContent = String(shown);
  $("#tab-agents-n").textContent = String(AGENTS.length);
  $("#tab-watch-n").textContent = String((d.watchlist || []).length);
}

// ---------- selection + detail panel ----------

function selectProject(id, { focus = false } = {}) {
  const report = state.reports.find((item) => item.id === id);
  state.selectedId = report ? report.id : null;
  lot.select(state.selectedId, { focus });
  if (!state.run) lot.setSignal(report ? verdictKey(report.recommendation) : null);
  renderDetail(report, state.details.get(report?.id));
  renderTracker();
  renderRoster();
  if (!report || state.details.has(report.id)) return;
  loadDetail(report.id)
    .then((payload) => {
      if (state.selectedId !== report.id) return;
      renderDetail(report, payload);
      renderTracker();
      renderRoster();
    })
    .catch((error) => toast(`Could not open that report: ${error.message}`));
}

function renderDetail(report, payload) {
  const panel = $("#detail");
  if (!report) {
    panel.innerHTML = `
      <p class="eyebrow">Empty lot</p>
      <h2>No projects yet</h2>
      <p class="detail-sub">Pitch a project and the agents will build its soundstage.</p>`;
    return;
  }
  const key = verdictKey(report.recommendation);
  const tone = key === "unknown" ? "idle" : key;
  const risk = Number(report.overall_risk_score);
  const confidence = Number(report.confidence) || 0;
  const scenarios = payload?.scenario_comparison || [];
  const subagents = payload?.subagent_results || {};
  const drivers = payload?.decision_drivers || [];

  panel.innerHTML = `
    <div class="detail-head">
      <span class="detail-glyph badge" data-v="${tone}">${slotLabel(report.slot)}</span>
      <div>
        <p class="eyebrow">Stage ${slotLabel(report.slot)} · ${esc(report.genre || "Unknown genre")}</p>
        <h2>${esc(report.project_name)}</h2>
        <p class="detail-sub">${esc(report.description)}</p>
      </div>
    </div>
    <div class="verdict-row">
      ${badge(report.recommendation)}
      <span>${Math.round(confidence * 100)}% confidence</span>
      <span>· ${esc(report.platform || "platform n/a")}</span>
    </div>
    <div class="tiles">
      <div class="tile">
        <p class="tile-label">Budget</p>
        <p class="tile-value">${money(report.budget)}</p>
      </div>
      <div class="tile">
        <p class="tile-label">Capital at risk</p>
        <p class="tile-value">${money(report.total_exposure)}</p>
      </div>
      <div class="tile">
        <p class="tile-label">Base ROI</p>
        <p class="tile-value">${percent(report.moderate_roi, 1)}</p>
        <div class="meter"><i data-v="${roiTone(report.moderate_roi)}" style="width:${clampPct(((Number(report.moderate_roi) || 0) + 50) / 1.5)}%"></i></div>
      </div>
      <div class="tile">
        <p class="tile-label">Risk score</p>
        <p class="tile-value">${Number.isFinite(risk) && report.overall_risk_score !== "" ? risk.toFixed(1) : "n/a"} <small>/ 10</small></p>
        <div class="meter"><i data-v="${riskTone(risk)}" style="width:${clampPct(risk * 10)}%"></i></div>
      </div>
    </div>

    <p class="section-title">Scenarios <span>ROI · gross revenue</span></p>
    <ul class="rows">
      ${
        scenarios.length
          ? scenarios
              .map(
                (row) => `
        <li>
          <span>${esc(row.case)}</span>
          <span class="num">${money(row.base_gross_revenue)}</span>
          <span class="badge" data-v="${roiTone(row.base_roi)}">${percent(row.base_roi, 1)}</span>
        </li>`
              )
              .join("")
          : `<li><span class="name">${payload ? "No scenario table in this report." : "Loading…"}</span></li>`
      }
    </ul>

    <p class="section-title">Agent desk <span>confidence</span></p>
    <ul class="rows agent-rows">
      ${AGENTS.map((agent) => {
        const value = Number(subagents[agent.key]?.confidence);
        const ok = Number.isFinite(value);
        return `
        <li>
          <span>${agent.short}</span>
          <div class="meter"><i style="width:${ok ? clampPct(value * 100) : 0}%"></i></div>
          <span class="num">${ok ? `${Math.round(value * 100)}%` : "–"}</span>
        </li>`;
      }).join("")}
    </ul>

    ${
      drivers.length
        ? `<p class="section-title">Decision drivers</p>
           <ul class="drivers">${drivers.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`
        : ""
    }

    ${
      report.is_sample
        ? `<p class="sample-note">Sample slate. These six projects are illustrative and disappear as soon as you run your first analysis.</p>`
        : `<div class="detail-actions">
             <a class="btn btn-ghost" href="/api/reports/${encodeURIComponent(report.id)}/brief-print" target="_blank" rel="noopener">Studio brief</a>
             <a class="btn btn-ghost" href="/api/reports/${encodeURIComponent(report.id)}/package">Pitch package</a>
           </div>`
    }`;
}

const clampPct = (value) => Math.max(0, Math.min(100, Number(value) || 0)).toFixed(0);

// ---------- pipeline tracker ----------

const STEP_ICONS = [
  '<path d="M6 3h6l3 3v11H6Z"/><path d="M8 9h5M8 12h5"/>',
  '<circle cx="9" cy="9" r="5"/><path d="m13 13 4 4"/>',
  '<circle cx="6" cy="7" r="2"/><circle cx="14" cy="7" r="2"/><path d="M2.5 16c.4-2.4 1.8-3.5 3.5-3.5s3.1 1.1 3.5 3.5M10.5 16c.4-2.4 1.8-3.5 3.5-3.5s3.1 1.1 3.5 3.5"/>',
  '<path d="M4 5h12M4 10h12M4 15h7"/>',
  '<path d="m4.5 10.5 3.5 3.5 7.5-8"/>',
];

function renderTracker() {
  const run = state.run;
  const report = state.reports.find((item) => item.id === state.selectedId);
  const payload = report ? state.details.get(report.id) : null;
  let steps;
  let subtitle;
  let card;

  if (run) {
    const s = run.steps;
    steps = [
      ["Intake", s.intake, s.intake === "done" ? "Accepted" : "Queued"],
      ["Market research", s.market, s.market === "done" ? "Comparables in" : s.market === "active" ? "Pulling comparables" : "Waiting"],
      ["Agent analysis", s.analysis, `${run.parallelDone}/${PARALLEL_AGENTS} agents`],
      ["Synthesis", s.synthesis, s.synthesis === "active" ? "Weighing evidence" : s.synthesis === "done" ? "Complete" : "Waiting"],
      ["Decision", s.decision, s.decision === "done" ? esc(run.verdict || "Ready") : "Pending"],
    ];
    subtitle = run.demo ? "Live run · demo mode" : "Live run";
    card = `
      <b>${esc(run.title)}</b>
      <small>${money(run.budget)} budget · ${esc(run.platform)}</small>
      <span><span class="badge" data-v="info">${run.failed ? "Failed" : "Analysing"}</span></span>`;
  } else if (report) {
    const comps = payload?.project?.comparables?.length;
    steps = [
      ["Intake", "done", esc(report.genre || "Logged")],
      ["Market research", "done", comps && !report.is_sample ? `${comps} comparables` : "Comparables in"],
      ["Agent analysis", "done", `${PARALLEL_AGENTS}/${PARALLEL_AGENTS} agents`],
      ["Synthesis", "done", `${Math.round((Number(report.confidence) || 0) * 100)}% confidence`],
      ["Decision", "done", esc(report.recommendation || "Unrated")],
    ];
    subtitle = `Stage ${slotLabel(report.slot)} · ${report.project_name}`;
    card = `
      <b>${esc(report.project_name)}</b>
      <small>${money(report.budget)} budget · ${esc(report.platform || "n/a")}${!report.is_sample && when(report.generated_at) ? ` · ${esc(when(report.generated_at))}` : ""}</small>
      <span>${badge(report.recommendation)}</span>`;
  } else {
    steps = ["Intake", "Market research", "Agent analysis", "Synthesis", "Decision"].map((label) => [label, "todo", "Waiting"]);
    subtitle = "Nothing selected";
    card = "<b>No project selected</b><small>Pick a soundstage or pitch a project.</small>";
  }

  $("#tracker").innerHTML = `
    <div class="tracker-head">
      <h3>Greenlight pipeline</h3>
      <p>${esc(subtitle)}</p>
    </div>
    <div class="steps">
      ${steps
        .map(
          ([label, status, sub], i) => `
        <div class="step" data-s="${status}">
          <span class="step-dot"><svg viewBox="0 0 20 20" aria-hidden="true">${STEP_ICONS[i]}</svg></span>
          <b>${label}</b>
          <small>${sub}</small>
        </div>`
        )
        .join("")}
    </div>
    <div class="tracker-card">${card}</div>`;
}

// ---------- roster (bottom-right tabs) ----------

function agentStatusText(key) {
  const status = state.agentStates[key];
  if (status === "working") return "Working on the live run";
  if (status === "done") return "Report filed";
  return "Idle";
}

function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tabs button").forEach((button) => {
    button.setAttribute("aria-selected", String(button.dataset.tab === tab));
  });
  renderRoster();
}

document.querySelector(".tabs").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-tab]");
  if (button) setTab(button.dataset.tab);
});

function renderRoster() {
  const list = $("#roster-list");
  if (state.tab === "agents") {
    const payload = state.details.get(state.selectedId);
    list.innerHTML = AGENTS.map((agent) => {
      const status = state.agentStates[agent.key];
      const tone = status === "working" ? "info" : status === "done" ? "go" : "idle";
      const text = status === "working" ? "Working" : status === "done" ? "Done" : "Idle";
      const value = Number(payload?.subagent_results?.[agent.key]?.confidence);
      return `
        <li class="agent" data-agent="${agent.key}">
          <span class="slot">${agent.short}</span>
          <span class="name">${agent.name}</span>
          <span class="badge" data-v="${tone}">${text}</span>
          <span class="num">${Number.isFinite(value) && !state.run ? `${Math.round(value * 100)}%` : "–"}</span>
        </li>`;
    }).join("");
    return;
  }

  let rows;
  if (state.tab === "watch") {
    rows = (state.dashboard?.watchlist || [])
      .map((item) => state.reports.find((report) => report.id === item.id))
      .filter(Boolean);
  } else {
    rows = [...state.reports].reverse();
  }
  if (!rows.length) {
    list.innerHTML = `<li class="empty">Nothing here yet.</li>`;
    return;
  }
  list.innerHTML = rows
    .map((report) => {
      const isWatch = state.tab === "watch";
      const riskOk = report.overall_risk_score !== "" && Number.isFinite(Number(report.overall_risk_score));
      const middle = isWatch
        ? `<span class="badge" data-v="${riskTone(report.overall_risk_score)}">${esc(report.risk_level || "Risk n/a")}</span>`
        : badge(report.recommendation);
      const right = isWatch ? (riskOk ? `${Number(report.overall_risk_score).toFixed(1)}/10` : "–") : percent(report.moderate_roi, 0);
      return `
        <li tabindex="0" data-id="${esc(report.id)}" aria-current="${report.id === state.selectedId}">
          <span class="slot">Stage ${slotLabel(report.slot)}</span>
          <span class="name">${esc(report.project_name)}</span>
          ${middle}
          <span class="num">${right}</span>
        </li>`;
    })
    .join("");
}

function rosterActivate(event) {
  if (event.type === "keydown" && event.key !== "Enter" && event.key !== " ") return;
  const row = event.target.closest("li[data-id]");
  if (!row) return;
  event.preventDefault();
  selectProject(row.dataset.id, { focus: true });
}
$("#roster-list").addEventListener("click", rosterActivate);
$("#roster-list").addEventListener("keydown", rosterActivate);

// ---------- search ----------

const searchInput = $("#search");
const searchResults = $("#search-results");

function runSearch() {
  const query = searchInput.value.trim().toLowerCase();
  if (!query) {
    searchResults.hidden = true;
    return [];
  }
  const matches = state.reports.filter((report) =>
    [report.project_name, report.description, report.genre, report.platform, report.recommendation, `stage ${slotLabel(report.slot)}`]
      .join(" ")
      .toLowerCase()
      .includes(query)
  );
  searchResults.innerHTML = matches.length
    ? matches
        .map(
          (report) =>
            `<li data-id="${esc(report.id)}"><span>Stage ${slotLabel(report.slot)} · ${esc(report.project_name)}</span>${badge(report.recommendation)}</li>`
        )
        .join("")
    : `<li class="empty">No projects match.</li>`;
  searchResults.hidden = false;
  return matches;
}

searchInput.addEventListener("input", runSearch);
searchInput.addEventListener("focus", runSearch);
searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    searchInput.value = "";
    searchResults.hidden = true;
  }
  if (event.key === "Enter") {
    const [first] = runSearch();
    if (first) {
      selectProject(first.id, { focus: true });
      searchResults.hidden = true;
      searchInput.blur();
    }
  }
});
searchResults.addEventListener("mousedown", (event) => {
  const row = event.target.closest("li[data-id]");
  if (!row) return;
  event.preventDefault();
  selectProject(row.dataset.id, { focus: true });
  searchResults.hidden = true;
});
searchInput.addEventListener("blur", () => {
  searchResults.hidden = true;
});

// ---------- pitch dialog + live run ----------

const pitch = $("#pitch");
const pitchForm = $("#pitch-form");
let samplePrefilled = false;

async function openPitch() {
  if (state.run) {
    toast("An analysis is already running.");
    return;
  }
  if (!samplePrefilled) {
    try {
      const sample = await getJSON("/api/sample");
      for (const name of ["description", "budget", "genre", "platform", "comparables", "target_audience"]) {
        if (sample[name] !== undefined) pitchForm.elements[name].value = sample[name];
      }
    } catch {
      /* leave the form blank */
    }
    samplePrefilled = true;
  }
  pitch.showModal();
}

$("#pitch-open").addEventListener("click", openPitch);
$("#pitch-close").addEventListener("click", () => pitch.close());

pitchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(pitchForm);
  const body = {
    description: String(form.get("description") || "").trim(),
    budget: Number(form.get("budget")) || 0,
    genre: String(form.get("genre") || "Unknown").trim() || "Unknown",
    platform: form.get("platform"),
    comparables: String(form.get("comparables") || ""),
    target_audience: String(form.get("target_audience") || "").trim() || "general",
    demo_mode: form.get("demo_mode") === "on",
  };
  // Blank means "let the finance model pick its default"; only send a number the user typed.
  const marketing = String(form.get("marketing_spend") ?? "").trim();
  if (marketing !== "" && Number.isFinite(Number(marketing))) body.marketing_spend = Math.max(0, Math.round(Number(marketing)));
  const submit = $("#pitch-submit");
  submit.disabled = true;
  try {
    const job = await getJSON("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    pitch.close();
    startRun(job, body);
  } catch (error) {
    toast(`Could not start the analysis: ${error.message}`);
  } finally {
    submit.disabled = false;
  }
});

function setAgent(key, status) {
  state.agentStates[key] = status;
  lot.setAgentState(key, status);
}

function startRun(job, body) {
  const words = body.description.split(/\s+/);
  state.run = {
    id: job.job_id,
    title: words.length > 6 ? `${words.slice(0, 6).join(" ")}…` : body.description,
    budget: body.budget,
    platform: body.platform,
    demo: body.demo_mode,
    steps: { intake: "active", market: "todo", analysis: "todo", synthesis: "todo", decision: "todo" },
    parallelDone: 0,
    verdict: "",
    failed: false,
  };
  AGENTS.forEach((agent) => setAgent(agent.key, "idle"));
  lot.setSignal("thinking");
  setTab("agents");
  renderTracker();

  // Demo-mode events arrive within milliseconds; pace them so the lot can act them out.
  const queue = [];
  let draining = false;
  const drain = async () => {
    if (draining) return;
    draining = true;
    while (queue.length) {
      await applyRunEvent(queue.shift());
      await new Promise((resolve) => setTimeout(resolve, EVENT_PACING_MS));
    }
    draining = false;
  };

  const source = new EventSource(job.events_url);
  source.onmessage = (message) => {
    const event = JSON.parse(message.data);
    queue.push(event);
    if (event.stage === "job" && (event.status === "completed" || event.status === "failed")) source.close();
    drain();
  };
  source.onerror = () => {
    source.close();
    if (state.run && !queue.length && state.run.steps.decision !== "done") {
      queue.push({ stage: "job", status: "failed", error: "Lost the connection to the analysis job." });
      drain();
    }
  };
}

async function applyRunEvent(event) {
  const run = state.run;
  if (!run) return;
  const s = run.steps;
  if (event.stage === "job" && event.status === "started") {
    s.intake = "done";
  } else if (event.stage === "agent") {
    const isMarket = event.name === "market_research";
    if (event.status === "started") {
      setAgent(event.name, "working");
      s.intake = "done";
      if (isMarket) s.market = "active";
      else {
        s.market = "done";
        s.analysis = "active";
      }
    } else if (event.status === "completed") {
      setAgent(event.name, "done");
      lot.dispatchCourier(event.name);
      if (isMarket) s.market = "done";
      else {
        run.parallelDone = Math.min(run.parallelDone + 1, PARALLEL_AGENTS);
        if (run.parallelDone >= PARALLEL_AGENTS) s.analysis = "done";
      }
    }
  } else if (event.stage === "synthesis") {
    s.analysis = "done";
    s.synthesis = event.status === "completed" ? "done" : "active";
  } else if (event.stage === "job" && event.status === "completed") {
    s.synthesis = "done";
    s.decision = "done";
    try {
      const job = await getJSON(`/api/jobs/${run.id}`);
      run.verdict = job.recommendation || "";
    } catch {
      /* the reloaded slate still carries the verdict */
    }
    renderTracker();
    await new Promise((resolve) => setTimeout(resolve, 900));
    state.run = null;
    state.details.clear();
    AGENTS.forEach((agent) => setAgent(agent.key, "idle"));
    await loadSlate({ selectNewest: true });
    setTab("slate");
    toast(run.verdict ? `Verdict in: ${run.verdict}` : "Analysis complete");
    return;
  } else if (event.stage === "job" && event.status === "failed") {
    run.failed = true;
    renderTracker();
    toast(`Analysis failed: ${event.error || "unknown error"}`);
    state.run = null;
    AGENTS.forEach((agent) => setAgent(agent.key, "idle"));
    selectProject(state.selectedId);
    return;
  }
  renderTracker();
  renderRoster();
}

// ---------- toast, clock, boot ----------

let toastTimer;
function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.hidden = true;
  }, 4200);
}

function tick() {
  $("#clock").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}
tick();
setInterval(tick, 15000);

renderTracker();
loadSlate().then(syncInsets);
