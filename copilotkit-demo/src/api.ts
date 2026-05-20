import type { GreenlightState, WorkflowEvent } from "./types";

const API_BASE = import.meta.env.VITE_GREENLIGHT_API_BASE || "/greenlight-api";

type JobStatus = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  error?: string;
  recommendation?: string;
  confidence?: number | string;
  download_markdown_url?: string;
  analysis_json_path?: string;
  scenario_comparison?: unknown[];
};

export async function startGreenlightAnalysis(state: GreenlightState): Promise<string> {
  const response = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      description: state.title,
      budget: state.budget,
      genre: state.genre,
      platform: state.platform,
      comparables: state.comparables.filter((item) => item.selected).map((item) => item.title).join(","),
      target_audience: state.targetAudience,
      demo_mode: true,
      comparable_source: "tmdb",
      private_dataset_id: "",
      marketing_spend: 9_000_000,
      distribution_fee_pct: 0.12,
      theatrical_revenue_share: 0.5,
      streaming_license_value: 0,
      subscriber_lifetime_value: 120,
      downside_revenue_multiplier: 1.4,
      base_revenue_multiplier: 2.6,
      upside_revenue_multiplier: 4.2,
      risk_tolerance: state.riskTolerance,
      source_material_name: state.title,
      source_material_text: state.description
    })
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  const body = await response.json() as { job_id: string };
  return body.job_id;
}

export function subscribeToJobEvents(jobId: string, onEvent: (event: WorkflowEvent) => void): EventSource {
  const source = new EventSource(`${API_BASE}/jobs/${jobId}/events`);
  source.onmessage = (message) => {
    const event = JSON.parse(message.data) as WorkflowEvent;
    onEvent(event);
  };
  return source;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<JobStatus>;
}

export async function getJobReport(jobId: string): Promise<string> {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/report`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.text();
}

export function packageUrl(reportId: string): string {
  return `${API_BASE}/reports/${encodeURIComponent(reportId)}/package`;
}

export function markdownDownloadUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/download/markdown`;
}
