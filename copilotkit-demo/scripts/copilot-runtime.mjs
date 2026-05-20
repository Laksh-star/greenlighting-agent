import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import process from "node:process";
import OpenAI from "openai";
import { CopilotRuntime, copilotRuntimeNodeHttpEndpoint } from "@copilotkit/runtime";

const HOST = process.env.COPILOT_RUNTIME_HOST || "127.0.0.1";
const PORT = Number(process.env.COPILOT_RUNTIME_PORT || 4010);
const BASE_PATH = process.env.COPILOT_RUNTIME_BASE_PATH || "/api/copilotkit";

loadEnvFile(resolve(process.cwd(), ".env.local"));
if (process.env.GREENLIGHT_ENV_FILE) loadEnvFile(process.env.GREENLIGHT_ENV_FILE);

const PROVIDER = process.env.OPENAI_API_KEY ? "openai" : process.env.ANTHROPIC_API_KEY ? "anthropic" : "none";
const MODEL = process.env.OPENAI_MODEL ||
  process.env.ANTHROPIC_MODEL ||
  process.env.MODEL_NAME ||
  (PROVIDER === "anthropic" ? "claude-sonnet-4-6" : "gpt-5.4-mini");

function loadEnvFile(path) {
  try {
    const body = readFileSync(path, "utf8");
    for (const line of body.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
      const [rawKey, ...rawValue] = trimmed.split("=");
      const key = rawKey.trim();
      const value = rawValue.join("=").trim().replace(/^['"]|['"]$/g, "");
      if (key && process.env[key] === undefined) process.env[key] = value;
    }
  } catch {
    // .env.local is optional; shell env vars work too.
  }
}

function latestUserText(input) {
  const messages = Array.isArray(input?.messages) ? input.messages : [];
  const latest = [...messages].reverse().find((message) => message.role === "user");
  const content = latest?.content;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .filter((part) => part?.type === "text")
      .map((part) => part.text)
      .join(" ")
      .trim();
  }
  return "";
}

function readGreenlightState(input) {
  if (input?.state && typeof input.state === "object") return input.state;
  const contexts = Array.isArray(input?.context) ? input.context : [];
  for (const item of contexts) {
    const value = item?.value;
    if (typeof value !== "string" || !value.includes('"title"')) continue;
    try {
      return JSON.parse(value);
    } catch {
      continue;
    }
  }
  return {};
}

function compactState(state) {
  const comparables = Array.isArray(state.comparables)
    ? state.comparables
        .filter((item) => item?.selected !== false)
        .map((item) => ({
          title: item.title,
          year: item.year,
          budget: item.budget,
          gross: item.gross,
          rationale: item.rationale
        }))
    : [];

  return {
    title: state.title,
    logline: state.logline,
    genre: state.genre,
    budget: state.budget,
    releaseShape: state.platform,
    backendStatus: state.backendStatus,
    recommendation: state.recommendation,
    confidence: state.confidence,
    riskScore: state.riskScore,
    approvals: {
      evidence: Boolean(state.comparablesApproved),
      assumptions: Boolean(state.assumptionsApproved),
      recommendation: Boolean(state.recommendationApproved),
      packageLocked: Boolean(state.packageLocked)
    },
    comparables,
    reportExcerpt: typeof state.reportMarkdown === "string"
      ? state.reportMarkdown.slice(0, 5000)
      : ""
  };
}

function event(type, payload = {}) {
  return { type, ...payload };
}

function emitText(onEvent, runId, messageId, text) {
  onEvent({ event: event("RUN_STARTED", { runId }) });
  onEvent({ event: event("TEXT_MESSAGE_START", { messageId, role: "assistant" }) });
  onEvent({ event: event("TEXT_MESSAGE_CONTENT", { messageId, delta: text }) });
  onEvent({ event: event("TEXT_MESSAGE_END", { messageId }) });
  onEvent({ event: event("RUN_FINISHED", { runId }) });
}

function createOpenAIGreenlightAgent() {
  return {
    clone: () => {
      const instance = {
        headers: {},
        threadId: undefined,
        setMessages: () => undefined,
        setState: () => undefined,
        runAgent: async (input, { onEvent }) => {
          const runId = input?.runId || `greenlight-run-${Date.now()}`;
          const messageId = `greenlight-openai-${Date.now()}`;
          const prompt = latestUserText(input) || "Review this greenlight decision.";
          const state = compactState(readGreenlightState(input));

          onEvent({
            event: event("STATE_SNAPSHOT", {
              snapshot: {
                stage: `${PROVIDER}-runtime`,
                model: MODEL,
                backendStatus: state.backendStatus,
                recommendation: state.recommendation
              }
            })
          });

          if (PROVIDER === "none") {
            emitText(
              onEvent,
              runId,
              messageId,
              "The CopilotKit runtime is running, but no LLM API key is configured. Add OPENAI_API_KEY or ANTHROPIC_API_KEY to .env.local, or set GREENLIGHT_ENV_FILE to the existing Greenlighting Agent .env file, then restart npm run copilot:runtime. Until then, use the default local fallback mode for no-key demo runs."
            );
            return;
          }

          const answer = PROVIDER === "openai"
            ? await runOpenAICompletion(state, prompt)
            : await runAnthropicCompletion(state, prompt);

          emitText(onEvent, runId, messageId, answer);
        }
      };
      return instance;
    }
  };
}

function systemPrompt() {
  return [
    "You are the Studio Greenlight Copilot inside a film greenlighting decision room.",
    "Use only the provided greenlight state and report excerpt.",
    "If backendStatus is not completed, ask the user to run the analysis first.",
    "Be concise, practical, and specific to the decision workflow.",
    "When relevant, mention the next UI action: approve evidence, approve decision, or lock package.",
    "Avoid emoji and long markdown sections; use short paragraphs or compact bullets."
  ].join(" ");
}

async function runOpenAICompletion(state, prompt) {
  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const completion = await client.chat.completions.create({
    model: MODEL,
    temperature: 0.3,
    messages: [
      { role: "system", content: systemPrompt() },
      {
        role: "user",
        content: `Current greenlight state:\n${JSON.stringify(state, null, 2)}\n\nUser question:\n${prompt}`
      }
    ]
  });

  return completion.choices[0]?.message?.content || "I could not generate a response from the OpenAI runtime.";
}

async function runAnthropicCompletion(state, prompt) {
  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": process.env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01"
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: Number(process.env.MAX_TOKENS || 900),
      temperature: 0.3,
      system: systemPrompt(),
      messages: [
        {
          role: "user",
          content: `Current greenlight state:\n${JSON.stringify(state, null, 2)}\n\nUser question:\n${prompt}`
        }
      ]
    })
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Anthropic runtime request failed: ${response.status} ${errorText.slice(0, 300)}`);
  }

  const payload = await response.json();
  const text = Array.isArray(payload.content)
    ? payload.content.filter((part) => part.type === "text").map((part) => part.text).join("\n")
    : "";
  return text || "I could not generate a response from the Anthropic runtime.";
}

const runtime = new CopilotRuntime({
  agents: {
    default: createOpenAIGreenlightAgent()
  }
});

const copilotHandler = copilotRuntimeNodeHttpEndpoint({
  runtime,
  endpoint: BASE_PATH,
  baseUrl: BASE_PATH,
  cors: {
    origin: ["http://127.0.0.1:5173", "http://localhost:5173"],
    allowMethods: ["GET", "POST", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization", "x-copilotkit-runtime-client-gql-version"]
  }
});

const server = createServer((req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host}`);

  if (url.pathname === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      ok: true,
      basePath: BASE_PATH,
      provider: PROVIDER,
      model: MODEL,
      openaiKeyConfigured: Boolean(process.env.OPENAI_API_KEY),
      anthropicKeyConfigured: Boolean(process.env.ANTHROPIC_API_KEY)
    }));
    return;
  }

  if (url.pathname.startsWith(BASE_PATH)) {
    return copilotHandler(req, res);
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not found", basePath: BASE_PATH }));
});

server.listen(PORT, HOST, () => {
  console.log(`CopilotKit runtime listening on http://${HOST}:${PORT}${BASE_PATH}`);
  console.log(`Provider: ${PROVIDER}`);
  console.log(`Model: ${MODEL}`);
});
