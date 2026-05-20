import React, { useReducer, useState } from "react";
import { createRoot } from "react-dom/client";
import { CopilotChat, CopilotKitProvider } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";
import "../styles.css";
import { getJobReport, getJobStatus, markdownDownloadUrl, packageUrl, startGreenlightAnalysis, subscribeToJobEvents } from "./api";
import { initialState, steps } from "./data";
import { ComparableCard } from "./components/GreenlightCards";
import { useGreenlightCopilotRegistrations } from "./copilotRegistrations";
import { localGreenlightAgent } from "./localGreenlightAgent";
import type { GreenlightAction, GreenlightState } from "./types";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

function reducer(state: GreenlightState, action: GreenlightAction): GreenlightState {
  switch (action.type) {
    case "set_state":
      return { ...state, ...action.patch };
    case "toggle_comparable":
      return {
        ...state,
        comparablesApproved: false,
        comparables: state.comparables.map((item, index) =>
          index === action.index ? { ...item, selected: !item.selected } : item
        )
      };
    case "approve_comparables":
      return { ...state, comparablesApproved: action.approved };
    case "approve_assumptions":
      return { ...state, assumptionsApproved: action.approved };
    case "approve_recommendation":
      return { ...state, recommendationApproved: action.approved };
    case "append_event":
      return { ...state, events: [...state.events, action.event].slice(-20) };
    case "reset":
      return initialState;
    default:
      return state;
  }
}

function StudioGreenlightApp() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [activeTab, setActiveTab] = useState("brief");
  const [error, setError] = useState("");

  useGreenlightCopilotRegistrations(state, (action) => {
    if (action.type === "set_tab") setActiveTab(action.tab);
    dispatch(action);
  });

  const approvalsReady = state.comparablesApproved && state.assumptionsApproved && state.recommendationApproved;
  const decisionApproved = state.assumptionsApproved && state.recommendationApproved;

  function approveEvidence() {
    dispatch({ type: "approve_comparables", approved: true });
    dispatch({ type: "set_state", patch: { workflowIndex: Math.max(state.workflowIndex, 3) } });
  }

  function approveDecision() {
    dispatch({ type: "approve_comparables", approved: true });
    dispatch({ type: "approve_assumptions", approved: true });
    dispatch({ type: "approve_recommendation", approved: true });
    dispatch({ type: "set_state", patch: { workflowIndex: 4 } });
    setActiveTab("package");
  }

  async function runExistingBackend() {
    setError("");
    dispatch({ type: "set_state", patch: { backendStatus: "running", workflowIndex: 1, events: [] } });
    try {
      const jobId = await startGreenlightAnalysis(state);
      dispatch({ type: "set_state", patch: { jobId } });
      const source = subscribeToJobEvents(jobId, (event) => {
        dispatch({ type: "append_event", event });
        if (event.status === "completed") dispatch({ type: "set_state", patch: { workflowIndex: 3 } });
      });

      const poll = window.setInterval(async () => {
        const status = await getJobStatus(jobId);
        if (status.status === "completed" || status.status === "failed") {
          window.clearInterval(poll);
          source.close();
          if (status.status === "failed") {
            dispatch({ type: "set_state", patch: { backendStatus: "failed" } });
            setError(status.error || "Greenlighting backend failed.");
            return;
          }
          const report = await getJobReport(jobId);
          dispatch({
            type: "set_state",
            patch: {
              backendStatus: "completed",
              workflowIndex: 4,
              recommendation: status.recommendation || "CONDITIONAL GO",
              confidence: status.confidence ? `${status.confidence}` : "78%",
              riskScore: "See report",
              reportMarkdown: report,
              reportId: status.analysis_json_path ? status.analysis_json_path.split("/").pop()?.replace(".json", "") || "" : ""
            }
          });
          setActiveTab("report");
        }
      }, 900);
    } catch (caught) {
      dispatch({ type: "set_state", patch: { backendStatus: "offline" } });
      setError(caught instanceof Error ? caught.message : "Could not reach Greenlighting backend.");
    }
  }

  function lockPackage() {
    if (!approvalsReady) {
      setError("Approve comparables, assumptions, and recommendation before locking package export.");
      return;
    }
    setError("");
    dispatch({ type: "set_state", patch: { packageLocked: true, workflowIndex: 4 } });
    setActiveTab("package");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Studio greenlight desk</p>
          <h1>Decision Room</h1>
        </div>
        <div className="topbar-actions">
          <button className="icon-button" onClick={() => dispatch({ type: "reset" })} title="Reset demo" aria-label="Reset demo">↺</button>
          <a className={`primary-action link-action ${state.jobId ? "" : "disabled"}`} href={state.jobId ? markdownDownloadUrl(state.jobId) : "#"}>Report</a>
          <a className={`primary-action link-action ${state.reportId && state.packageLocked ? "" : "disabled"}`} href={state.reportId && state.packageLocked ? packageUrl(state.reportId) : "#"}>Package</a>
        </div>
      </header>

      <main className="workspace">
        <section className="canvas-pane" aria-label="Greenlight workspace">
          <DecisionHero state={state} />
          <DecisionFlow state={state} />
          <div className="command-strip">
            <button className="primary-action" onClick={runExistingBackend} disabled={state.backendStatus === "running"}>
              {state.backendStatus === "running" ? "Analysis running" : "Run Greenlight Analysis"}
            </button>
            <button className={`secondary-action ${state.comparablesApproved ? "selected" : ""}`} onClick={approveEvidence}>
              {state.comparablesApproved ? "Evidence Approved" : "Approve Evidence"}
            </button>
            <button className={`secondary-action ${decisionApproved ? "selected" : ""}`} onClick={approveDecision}>
              {decisionApproved ? "Decision Approved" : "Approve Decision"}
            </button>
          </div>
          <ApprovalStatusStrip state={state} />
          <div className="studio-grid">
            <AgentRunPanel state={state} />
            <GenerativeSurface state={state} dispatch={dispatch} />
            <A2UIDecisionObject state={state} />
            <HumanGatePanel state={state} dispatch={dispatch} lockPackage={lockPackage} />
          </div>
          <section className="report-drawer">
            <div className="drawer-header">
              <div>
                <p className="eyebrow">Backend artifact</p>
                <h2>{activeTab === "package" ? "Pitch package readiness" : "Generated report preview"}</h2>
                <span className="copilot-control-badge">CopilotKit: backend bridge</span>
              </div>
              <button className="tab" onClick={() => setActiveTab(activeTab === "report" ? "package" : "report")}>
                {activeTab === "report" ? "Show Package" : "Show Report"}
              </button>
            </div>
            {activeTab === "package" ? <PackagePanel state={state} dispatch={dispatch} lockPackage={lockPackage} /> : <ReportPanel state={state} />}
          </section>
        </section>

        <section className="chat-pane" aria-label="Greenlight copilot">
          <div className="pane-header agent-header">
            <div>
              <h2>Greenlight Copilot</h2>
              <p>{state.backendStatus === "completed"
                ? "Ask about the completed report, weak comps, unresolved approvals, or package readiness."
                : "Run the greenlight analysis first; Copilot then explains the result and helps move the decision forward."}</p>
            </div>
            <span className="status-dot">{state.backendStatus}</span>
          </div>
          <CopilotReadiness state={state} />
          <div className="copilot-host">
            <CopilotChat
              labels={{
                modalHeaderTitle: "Greenlight Copilot",
                welcomeMessageText: state.backendStatus === "completed"
                  ? "The analysis is ready. Ask me why the recommendation landed here, which evidence matters, or what is still blocking package export."
                  : "Run Greenlight Analysis first. I will use the generated report and approval state to help you review the decision.",
                chatInputPlaceholder: state.backendStatus === "completed"
                  ? "Ask about this report, comps, gates, or package..."
                  : "After analysis, ask about the result..."
              }}
            />
          </div>
          {error ? <p className="error-text">{error}</p> : null}
        </section>
      </main>
    </div>
  );
}

function CopilotReadiness({ state }: { state: GreenlightState }) {
  const reportReady = state.backendStatus === "completed";
  const approved = [
    state.comparablesApproved ? "Evidence" : "",
    state.assumptionsApproved ? "Assumptions" : "",
    state.recommendationApproved ? "Recommendation" : ""
  ].filter(Boolean);

  return (
    <div className={`copilot-brief ${reportReady ? "ready" : ""}`}>
      <span>{reportReady ? "Report context loaded" : "Waiting for backend analysis"}</span>
      <strong>{reportReady ? `${state.recommendation} · ${state.confidence}` : "Copilot activates after the run"}</strong>
      <small>{reportReady
        ? `${approved.length}/3 approval gates cleared`
        : "Use the main Run Greenlight Analysis button in the decision workspace."}</small>
    </div>
  );
}

function ApprovalStatusStrip({ state }: { state: GreenlightState }) {
  const gates = [
    ["Evidence", state.comparablesApproved],
    ["Assumptions", state.assumptionsApproved],
    ["Recommendation", state.recommendationApproved],
    ["Package", state.packageLocked]
  ] as const;

  return (
    <section className="approval-status-strip" aria-label="Approval status">
      {gates.map(([label, done]) => (
        <div className={done ? "done" : ""} key={label}>
          <span>{done ? "✓" : "○"}</span>
          <strong>{label}</strong>
        </div>
      ))}
    </section>
  );
}

function DecisionFlow({ state }: { state: GreenlightState }) {
  const approvalsReady = state.comparablesApproved && state.assumptionsApproved && state.recommendationApproved;
  const flow = [
    ["1", "Brief", "Project and starting assumptions", true],
    ["2", "Analysis", "Run the greenlight agent", state.backendStatus === "running" || state.backendStatus === "completed"],
    ["3", "Review", "Read evidence and report", state.backendStatus === "completed"],
    ["4", "Approve", "Clear gates and lock package", approvalsReady || state.packageLocked]
  ] as const;

  return (
    <section className="decision-flow" aria-label="Greenlight workflow">
      {flow.map(([number, title, description, active]) => (
        <article className={active ? "active" : ""} key={title}>
          <span>{number}</span>
          <div>
            <strong>{title}</strong>
            <small>{description}</small>
          </div>
        </article>
      ))}
    </section>
  );
}

function DecisionHero({ state }: { state: GreenlightState }) {
  return (
    <section className="decision-hero">
      <div>
        <p className="eyebrow">Agent-native decision workspace</p>
        <h2>{state.title}</h2>
        <p>{state.description}</p>
        <div className="hero-meta">
          <span>{currency.format(state.budget)} budget</span>
          <span>{state.genre}</span>
          <span>{state.platform} release</span>
          <span>{state.targetAudience}</span>
        </div>
      </div>
      <div className="hero-score">
        <span>{state.recommendation}</span>
        <strong>{state.confidence}</strong>
        <small>confidence</small>
      </div>
    </section>
  );
}

function AgentRunPanel({ state }: { state: GreenlightState }) {
  const stream = state.events.length
    ? state.events
    : steps.map((step, index) => ({
      stage: step,
      name: step,
      status: index < state.workflowIndex ? "done" : index === state.workflowIndex ? "active" : "waiting"
    }));

  return (
    <section className="live-panel run-panel">
      <div className="module-title">
        <div>
          <p className="eyebrow">Analysis desk</p>
          <h3>Greenlight run</h3>
        </div>
        <span className="copilot-control-badge">CopilotKit: context</span>
      </div>
      <div className="event-rail">
        {stream.map((event, index) => (
          <article className={`event-card ${event.status}`} key={`${event.name}-${index}`}>
            <span>{event.stage || `stage ${index + 1}`}</span>
            <strong>{event.name}</strong>
            <small>{event.status}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function GenerativeSurface({ state, dispatch }: { state: GreenlightState; dispatch: React.Dispatch<GreenlightAction> }) {
  return (
    <section className="live-panel generative-panel">
      <div className="module-title">
        <div>
          <p className="eyebrow">Comparable evidence</p>
          <h3>Selected titles</h3>
        </div>
        <span className="copilot-control-badge">CopilotKit: generative UI</span>
      </div>
      <div className="movie-grid modern">
        {state.comparables.map((movie, index) => (
          <ComparableCard key={movie.title} movie={movie} onToggle={() => dispatch({ type: "toggle_comparable", index })} />
        ))}
      </div>
    </section>
  );
}

function A2UIDecisionObject({ state }: { state: GreenlightState }) {
  const rows = [
    ["recommendation", state.recommendation],
    ["risk_model", state.riskScore],
    ["release_shape", state.platform],
    ["tool_output", state.reportId || "awaiting report id"]
  ];

  return (
    <section className="live-panel schema-panel">
      <div className="module-title">
        <div>
          <p className="eyebrow">Decision snapshot</p>
          <h3>Current signal</h3>
        </div>
        <span className="copilot-control-badge">CopilotKit: A2UI</span>
      </div>
      <div className="schema-object">
        {rows.map(([key, value]) => (
          <div className="schema-row" key={key}>
            <span>{key}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="signal-bars">
        <span style={{ width: "84%" }} />
        <span style={{ width: "62%" }} />
        <span style={{ width: "73%" }} />
      </div>
    </section>
  );
}

function HumanGatePanel({ state, dispatch, lockPackage }: { state: GreenlightState; dispatch: React.Dispatch<GreenlightAction>; lockPackage: () => void }) {
  const approvalsReady = state.comparablesApproved && state.assumptionsApproved && state.recommendationApproved;
  const checks = [
    ["Comparables", state.comparablesApproved, () => dispatch({ type: "approve_comparables", approved: !state.comparablesApproved })],
    ["Assumptions", state.assumptionsApproved, () => dispatch({ type: "approve_assumptions", approved: !state.assumptionsApproved })],
    ["Recommendation", state.recommendationApproved, () => dispatch({ type: "approve_recommendation", approved: !state.recommendationApproved })]
  ] as const;

  return (
    <section className="live-panel gate-panel">
      <div className="module-title">
        <div>
          <p className="eyebrow">Human-in-the-loop</p>
          <h3>Package approval gate</h3>
        </div>
        <span className="copilot-control-badge">CopilotKit: tools</span>
      </div>
      <div className="approval-stack">
        {checks.map(([label, checked, onClick]) => (
          <button className={`approval-chip ${checked ? "checked" : ""}`} onClick={onClick} key={label}>
            <span>{checked ? "✓" : "○"}</span>
            {label}
          </button>
        ))}
      </div>
      <button className="primary-action full-width" onClick={lockPackage} disabled={!approvalsReady || state.packageLocked}>
        {state.packageLocked ? "Package Locked" : "Lock Pitch Package"}
      </button>
    </section>
  );
}

function BriefPanel({ state }: { state: GreenlightState }) {
  return (
    <section className="tab-panel active">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Shared state canvas</p>
          <h2>{state.title}</h2>
        </div>
        <span className="recommendation">{state.recommendation}</span>
      </div>

      <div className="brief-grid">
        <article className="metric-block"><span>Budget</span><strong>{currency.format(state.budget)}</strong></article>
        <article className="metric-block"><span>Platform</span><strong>{state.platform}</strong></article>
        <article className="metric-block"><span>Risk</span><strong>{state.riskScore}</strong></article>
        <article className="metric-block"><span>Confidence</span><strong>{state.confidence}</strong></article>
      </div>

      <div className="workflow-strip">
        {steps.map((step, index) => (
          <article className={`workflow-step ${index < state.workflowIndex ? "done" : ""} ${index === state.workflowIndex ? "active" : ""}`} key={step}>
            <span>Step {index + 1}</span>
            <strong>{step}</strong>
          </article>
        ))}
      </div>

      <div className="two-column">
        <section>
          <h3>Decision Drivers</h3>
          <ul className="driver-list">{state.drivers.map((driver) => <li key={driver}>{driver}</li>)}</ul>
        </section>
        <section>
          <h3>Backend Events</h3>
          <div className="assumption-list">
            {state.events.length ? state.events.map((event, index) => (
              <div className="assumption-row" key={`${event.name}-${index}`}>
                <span>{event.name || event.stage}</span><strong>{event.status}</strong>
              </div>
            )) : state.assumptions.map(([label, value]) => (
              <div className="assumption-row" key={label}><span>{label}</span><strong>{value}</strong></div>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

function ComparablesPanel({ state, dispatch }: { state: GreenlightState; dispatch: React.Dispatch<GreenlightAction> }) {
  return (
    <section className="tab-panel active">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Controlled generative UI components</p>
          <h2>Comparable Title Cards</h2>
        </div>
        <button className="secondary-action" onClick={() => dispatch({ type: "approve_comparables", approved: true })}>Approve Comparables</button>
      </div>
      <div className="movie-grid">
        {state.comparables.map((movie, index) => (
          <ComparableCard key={movie.title} movie={movie} onToggle={() => dispatch({ type: "toggle_comparable", index })} />
        ))}
      </div>
    </section>
  );
}

function MatrixPanel({ state }: { state: GreenlightState }) {
  return (
    <section className="tab-panel active">
      <div className="section-heading">
        <div>
          <p className="eyebrow">A2UI-style declarative surface</p>
          <h2>Generated Decision Matrix</h2>
        </div>
      </div>
      <div className="matrix">
        <table>
          <thead><tr><th>Comparable</th><th>Budget</th><th>Revenue</th><th>Return</th><th>Agent label</th></tr></thead>
          <tbody>
            {state.comparables.filter((movie) => movie.selected).map((movie) => (
              <tr key={movie.title}>
                <td><strong>{movie.title}</strong><br />{movie.fit}</td>
                <td>{currency.format(movie.budget)}</td>
                <td>{currency.format(movie.revenue)}</td>
                <td>{movie.budget ? `${(movie.revenue / movie.budget).toFixed(1)}x` : "-"}</td>
                <td>{movie.title === "Arrival" ? "Upside comp" : "Core comp"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PackagePanel({ state, dispatch, lockPackage }: { state: GreenlightState; dispatch: React.Dispatch<GreenlightAction>; lockPackage: () => void }) {
  return (
    <section className="tab-panel active">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Human-in-the-loop</p>
          <h2>Pitch Package Gate</h2>
        </div>
        <span className="package-state">{state.packageLocked ? "Locked for export" : "Not approved"}</span>
      </div>
      <div className="package-layout">
        <section className="approval-panel">
          <h3>Before Export</h3>
          <label><input type="checkbox" checked={state.comparablesApproved} onChange={(event) => dispatch({ type: "approve_comparables", approved: event.target.checked })} /> Comparables approved</label>
          <label><input type="checkbox" checked={state.assumptionsApproved} onChange={(event) => dispatch({ type: "approve_assumptions", approved: event.target.checked })} /> Financial assumptions approved</label>
          <label><input type="checkbox" checked={state.recommendationApproved} onChange={(event) => dispatch({ type: "approve_recommendation", approved: event.target.checked })} /> Final recommendation accepted</label>
          <button className="primary-action" onClick={lockPackage} disabled={state.packageLocked}>
            {state.packageLocked ? "Package Locked" : "Lock Package"}
          </button>
        </section>
        <section>
          <h3>Existing Repo Package Contents</h3>
          <ul className="driver-list">
            <li>Studio decision memo</li>
            <li>Full greenlight report</li>
            <li>Financial scenario summary</li>
            <li>Comparable evidence</li>
            <li>Risk matrix and mitigation notes</li>
            <li>Run ledger</li>
          </ul>
        </section>
      </div>
    </section>
  );
}

function ReportPanel({ state }: { state: GreenlightState }) {
  return (
    <section className="tab-panel active">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Existing backend output</p>
          <h2>Generated Report Preview</h2>
        </div>
      </div>
      <pre className="report-preview">{state.reportMarkdown || "Run the existing Greenlighting backend to load a real report here."}</pre>
    </section>
  );
}

function Root() {
  const runtimeUrl = import.meta.env.VITE_COPILOTKIT_RUNTIME_URL as string | undefined;

  return (
    <CopilotKitProvider
      {...(runtimeUrl ? { runtimeUrl } : { agents__unsafe_dev_only: { default: localGreenlightAgent } })}
      showDevConsole={false}
      openGenerativeUI={{
        designSkill: "Generate compact studio-decision UI: evidence cards, approval gates, concise financial risk labels, and no marketing copy."
      }}
    >
      <StudioGreenlightApp />
    </CopilotKitProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
