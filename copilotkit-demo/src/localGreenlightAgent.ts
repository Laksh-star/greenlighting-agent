import { AbstractAgent, EventType, type BaseEvent, type RunAgentInput } from "@ag-ui/client";
import { Observable } from "rxjs";

let messageCounter = 0;

function getLatestUserText(input: RunAgentInput) {
  const latest = [...(input.messages || [])].reverse().find((message) => message.role === "user");
  if (!latest) return "Review this package.";
  if (typeof latest.content === "string") return latest.content;
  const textParts = latest.content
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join(" ");
  if (textParts.trim()) return textParts;
  return "Review this package.";
}

function readState(input: RunAgentInput) {
  const state = input.state as Record<string, unknown> | undefined;
  const contextState = input.context
    ?.map((item) => item.value)
    .find((value) => value.includes('"title"') && value.includes('"comparables"'));

  if (state?.title) return state;
  if (contextState) {
    try {
      return JSON.parse(contextState) as Record<string, unknown>;
    } catch {
      return {};
    }
  }
  return {};
}

function selectedComparables(state: Record<string, unknown>) {
  const comparables = Array.isArray(state.comparables) ? state.comparables : [];
  return comparables
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object" && "title" in item))
    .filter((item) => item.selected !== false)
    .map((item) => String(item.title));
}

function approvalStatus(state: Record<string, unknown>) {
  const approved = [
    state.comparablesApproved ? "evidence" : "",
    state.assumptionsApproved ? "assumptions" : "",
    state.recommendationApproved ? "recommendation" : ""
  ].filter(Boolean);

  const waiting = [
    !state.comparablesApproved ? "evidence" : "",
    !state.assumptionsApproved ? "assumptions" : "",
    !state.recommendationApproved ? "recommendation" : ""
  ].filter(Boolean);

  return { approved, waiting };
}

function buildResponse(prompt: string, state: Record<string, unknown>) {
  const title = String(state.title || "Lunar Drift");
  const budget = typeof state.budget === "number" ? `$${(state.budget / 1_000_000).toFixed(0)}M` : "$18M";
  const release = String(state.platform || "hybrid");
  const recommendation = String(state.recommendation || "Pending");
  const confidence = String(state.confidence || "-");
  const backendStatus = String(state.backendStatus || "idle");
  const comps = selectedComparables(state);
  const { approved, waiting } = approvalStatus(state);

  const wantsPackage = prompt.includes("package") || prompt.includes("export") || prompt.includes("lock");
  const wantsApproval = prompt.includes("approve") || prompt.includes("approval") || prompt.includes("gate");
  const wantsRisk = prompt.includes("risk") || prompt.includes("concern") || prompt.includes("downside");
  const wantsComps = prompt.includes("comp") || prompt.includes("evidence") || prompt.includes("comparable");
  const wantsBudget = prompt.includes("budget") || prompt.includes("cost") || prompt.includes("financial") || prompt.includes("assumption");
  const wantsRelease = prompt.includes("release") || prompt.includes("platform") || prompt.includes("theatrical") || prompt.includes("streaming");
  const wantsReport = prompt.includes("report") || prompt.includes("analysis") || prompt.includes("status") || prompt.includes("result");

  if (backendStatus !== "completed") {
    if (backendStatus === "running") {
      return `The greenlight analysis is still running. Once the backend report lands, I can explain the recommendation, identify the weakest evidence, and help clear the package gates.`;
    }
    return `I do not have the backend report yet, so I should not invent a greenlight view. Click Run Greenlight Analysis first; after that I can interpret the actual recommendation, confidence, comparable evidence, and package blockers.`;
  }

  if (wantsApproval) {
    return approved.length
      ? `Approval state for ${title}: ${approved.join(", ")} approved; still waiting on ${waiting.join(", ") || "nothing"}. If the report looks right, the next product action is to approve the remaining gate and lock the package.`
      : `Nothing is approved yet for ${title}. Start with evidence approval after reviewing the comps, then approve assumptions and final recommendation before locking the package.`;
  }

  if (wantsPackage) {
    return waiting.length
      ? `The package is not ready to lock. Waiting on ${waiting.join(", ")}. Once those gates are approved, the package link should include the decision memo, report, financial assumptions, risk notes, and approval record.`
      : `The package is ready to lock. The clean export story is: ${recommendation} at ${confidence} confidence, backed by ${comps.join(", ") || "the selected comp set"} and the completed approval record.`;
  }

  if (wantsComps) {
    return `${comps.join(", ") || "The current comp set"} is doing three different jobs: Ex Machina anchors contained AI thriller economics, Moon supports lean lunar production logic, and Arrival should be treated as upside evidence rather than the base case.`;
  }

  if (wantsBudget) {
    return `The ${budget} budget is credible only if ${title} stays contained: limited locations, capped VFX, and no franchise-scale action language. The financial assumption to watch is whether the base revenue multiple can cover production plus marketing.`;
  }

  if (wantsRelease) {
    return `The ${release} release shape is a sensible hedge. The pitch should lead with adult sci-fi credibility, use theatrical awareness if reviews are strong, and keep streaming/licensing optionality as downside protection.`;
  }

  if (wantsReport) {
    return `The current backend signal is ${recommendation} with ${confidence} confidence. Review the report preview, check the evidence gate, then approve the final decision if the assumptions still hold.`;
  }

  if (wantsRisk) {
    return `The main risk is scope creep: ${title} works as contained premium sci-fi, but weakens if the package implies large-scale space action. I would call out budget discipline, VFX limits, and a narrow adult sci-fi audience as the key mitigations.`;
  }

  return `For ${title}, I would first run the analysis, then pressure-test comps, assumptions, and release shape before locking the package. Ask me specifically about risk, comps, budget, release, approval status, or package readiness and I will focus there.`;
}

function textStart(messageId: string): BaseEvent {
  return { type: EventType.TEXT_MESSAGE_START, messageId, role: "assistant" } as BaseEvent;
}

function textDelta(messageId: string, delta: string): BaseEvent {
  return { type: EventType.TEXT_MESSAGE_CONTENT, messageId, delta } as BaseEvent;
}

function textEnd(messageId: string): BaseEvent {
  return { type: EventType.TEXT_MESSAGE_END, messageId } as BaseEvent;
}

function stateSnapshot(snapshot: unknown): BaseEvent {
  return { type: EventType.STATE_SNAPSHOT, snapshot } as BaseEvent;
}

export class LocalGreenlightAgent extends AbstractAgent {
  constructor() {
    super({
      agentId: "default",
      description: "Local Studio Greenlight Copilot agent for article demo runs."
    });
  }

  clone(): this {
    return new LocalGreenlightAgent() as this;
  }

  getCapabilities() {
    return Promise.resolve({
      identity: {
        type: "local",
        name: "Studio Greenlight Copilot",
        version: "1.57.3-v2-demo"
      },
      transport: {
        streaming: true
      },
      tools: {
        supported: true,
        clientProvided: true
      },
      state: {
        snapshots: true
      }
    });
  }

  run(input: RunAgentInput): Observable<BaseEvent> {
    const prompt = getLatestUserText(input).toLowerCase();
    const state = readState(input);
    const messageId = `local-greenlight-${Date.now()}-${messageCounter++}`;
    const wantsPackage = prompt.includes("package") || prompt.includes("approve") || prompt.includes("export");
    const wantsRisk = prompt.includes("risk") || prompt.includes("concern") || prompt.includes("downside");
    const wantsComps = prompt.includes("comp") || prompt.includes("evidence") || prompt.includes("comparable");
    const response = buildResponse(prompt, state);

    const events: BaseEvent[] = [
      { type: EventType.RUN_STARTED } as BaseEvent,
      stateSnapshot({
        stage: "local-copilot-analysis",
        packageIntent: wantsPackage,
        riskIntent: wantsRisk,
        comparableIntent: wantsComps
      }),
      textStart(messageId),
      textDelta(messageId, response),
      textEnd(messageId),
      { type: EventType.RUN_FINISHED } as BaseEvent
    ];

    return new Observable<BaseEvent>((subscriber) => {
      events.forEach((event, index) => {
        globalThis.setTimeout(() => {
          subscriber.next(event);
          if (index === events.length - 1) subscriber.complete();
        }, index * 120);
      });
    });
  }
}

export const localGreenlightAgent = new LocalGreenlightAgent();
