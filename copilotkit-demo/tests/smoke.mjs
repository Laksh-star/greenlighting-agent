import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const html = readFileSync(join(root, "index.html"), "utf8");
const css = readFileSync(join(root, "styles.css"), "utf8");
const app = readFileSync(join(root, "src/main.tsx"), "utf8");
const registrations = readFileSync(join(root, "src/copilotRegistrations.tsx"), "utf8");
const localAgent = readFileSync(join(root, "src/localGreenlightAgent.ts"), "utf8");
const api = readFileSync(join(root, "src/api.ts"), "utf8");
const runtime = readFileSync(join(root, "scripts/copilot-runtime.mjs"), "utf8");
const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));

const requiredDomIds = [
  "root"
];

const requiredFeatureTerms = [
  "CopilotKitProvider",
  "CopilotChat",
  "useAgentContext",
  "useComponent",
  "useFrontendTool",
  "LocalGreenlightAgent",
  "agents__unsafe_dev_only",
  "startGreenlightAnalysis",
  "/greenlight-api"
];

for (const id of requiredDomIds) {
  if (!html.includes(`id="${id}"`)) {
    throw new Error(`Missing DOM id: ${id}`);
  }
}

for (const term of requiredFeatureTerms) {
  const haystack = [app, registrations, localAgent, api].join("\n");
  if (!haystack.includes(term)) {
    throw new Error(`Missing feature term: ${term}`);
  }
}

const requiredRuntimeTerms = [
  "CopilotRuntime",
  "copilotRuntimeNodeHttpEndpoint",
  "OPENAI_API_KEY",
  "ANTHROPIC_API_KEY",
  "OpenAI",
  "api.anthropic.com",
  "/api/copilotkit"
];

for (const term of requiredRuntimeTerms) {
  if (!runtime.includes(term)) {
    throw new Error(`Missing runtime term: ${term}`);
  }
}

if (!pkg.scripts["copilot:runtime"] || !pkg.scripts["dev:runtime"]) {
  throw new Error("OpenAI-backed runtime scripts are missing");
}

if (!css.includes("@media (max-width: 900px)")) {
  throw new Error("Responsive mobile breakpoint missing");
}

if (!app.includes("Run Greenlight Analysis")) {
  throw new Error("Existing backend run control missing");
}

console.log("Smoke OK: CopilotKit 1.57/v2 Greenlight demo has required hooks, components, and backend integration points.");
