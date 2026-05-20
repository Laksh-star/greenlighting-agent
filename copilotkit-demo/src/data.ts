import type { GreenlightState } from "./types";

export const steps = [
  "Collect project",
  "Validate comps",
  "Run subagents",
  "Review decision",
  "Package export"
];

export const initialState: GreenlightState = {
  title: "Lunar Drift",
  description: "A contained sci-fi thriller about a lunar mining crew and a rogue AI.",
  budget: 18_000_000,
  genre: "Science Fiction",
  platform: "hybrid",
  targetAudience: "Adults 18-49, sci-fi thriller fans",
  riskTolerance: "balanced",
  workflowIndex: 0,
  backendStatus: "idle",
  jobId: "",
  reportId: "",
  reportMarkdown: "",
  recommendation: "Pending",
  confidence: "-",
  riskScore: "-",
  packageLocked: false,
  comparablesApproved: false,
  assumptionsApproved: false,
  recommendationApproved: false,
  comparables: [
    {
      title: "Ex Machina",
      year: 2015,
      rating: 7.6,
      budget: 15_000_000,
      revenue: 36_900_000,
      fit: "Contained AI thriller with premium adult positioning.",
      selected: true
    },
    {
      title: "Moon",
      year: 2009,
      rating: 7.6,
      budget: 5_000_000,
      revenue: 9_800_000,
      fit: "Lean lunar production model with strong genre credibility.",
      selected: true
    },
    {
      title: "Arrival",
      year: 2016,
      rating: 7.6,
      budget: 47_000_000,
      revenue: 203_400_000,
      fit: "Adult original sci-fi upside, but larger budget profile.",
      selected: true
    }
  ],
  drivers: [
    "Contained production footprint keeps downside exposure manageable.",
    "Comparable set supports a focused adult sci-fi audience.",
    "Hybrid release improves optionality if theatrical awareness is limited."
  ],
  assumptions: [
    ["Marketing spend", "$9.0M"],
    ["Distribution fee", "12%"],
    ["Base revenue multiple", "2.6x"],
    ["Risk tolerance", "Balanced"]
  ],
  events: []
};

export const workflowGuide = [
  ["Ask the copilot", "Use the chat to pressure-test risk, comparable logic, or package readiness."],
  ["Run analysis", "Start the existing Greenlighting Agent and watch the run events move through the workspace."],
  ["Review evidence", "Inspect comparable cards, scenario signals, and the generated report."],
  ["Approve gates", "Approve evidence, assumptions, and recommendation before export."],
  ["Export package", "Lock the pitch package and use the generated package link."]
];

export const showcasedFeatures = [
  ["Controlled Generative UI", "Registered React components render recommendation and package-gate cards with predictable studio styling."],
  ["Declarative UI / A2UI", "The decision object presents agent output as structured fields rather than a loose paragraph."],
  ["Open Generative UI", "The provider is configured for sandboxed generated UI when a runtime is attached."],
  ["Agent Context", "The copilot receives the current project, approvals, backend status, report id, and selected comparables."],
  ["Frontend Tools", "The copilot can open panels and mark approval checkpoints through registered frontend tools."],
  ["Existing Agent Bridge", "The demo calls the real FastAPI Greenlighting Agent job flow and streams backend events into the React workspace."]
];
