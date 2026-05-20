export type Comparable = {
  title: string;
  year: number;
  rating: number;
  budget: number;
  revenue: number;
  fit: string;
  selected: boolean;
};

export type WorkflowEvent = {
  stage: string;
  name: string;
  status: string;
  message?: string;
  error?: string;
};

export type GreenlightState = {
  title: string;
  description: string;
  budget: number;
  genre: string;
  platform: string;
  targetAudience: string;
  riskTolerance: string;
  workflowIndex: number;
  backendStatus: "offline" | "idle" | "running" | "completed" | "failed";
  jobId: string;
  reportId: string;
  reportMarkdown: string;
  recommendation: string;
  confidence: string;
  riskScore: string;
  packageLocked: boolean;
  comparablesApproved: boolean;
  assumptionsApproved: boolean;
  recommendationApproved: boolean;
  comparables: Comparable[];
  drivers: string[];
  assumptions: Array<[string, string]>;
  events: WorkflowEvent[];
};

export type GreenlightAction =
  | { type: "set_tab"; tab: string }
  | { type: "set_state"; patch: Partial<GreenlightState> }
  | { type: "toggle_comparable"; index: number }
  | { type: "approve_comparables"; approved: boolean }
  | { type: "approve_assumptions"; approved: boolean }
  | { type: "approve_recommendation"; approved: boolean }
  | { type: "append_event"; event: WorkflowEvent }
  | { type: "reset" };
