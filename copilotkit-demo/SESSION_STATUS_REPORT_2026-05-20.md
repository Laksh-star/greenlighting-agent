# Studio Greenlight Copilot - Session Status Report

Date: 2026-05-20
Repo path: `copilotkit-demo/` inside the Greenlighting Agent repository
Local app URL: `http://127.0.0.1:5173/`

## 1. Objective

The goal of this session was to turn the Greenlighting Agent idea into a stronger CopilotKit article demo, not just a static or dated UI. The demo needed to:

- Reuse the existing Greenlighting Agent backend flow where possible.
- Show current CopilotKit React usage rather than a hand-built chat mock.
- Make the app feel like a real decision workspace for a film/TV greenlight process.
- Demonstrate more than chat: shared context, app control, generative UI, backend state, and human approval gates.
- Improve confusing flow and visual clunkiness reported during browser testing.
- Provide enough technical substance to support a Medium article.

## 2. Current CopilotKit Version Position

We verified the latest CopilotKit release from the CopilotKit GitHub releases page during the session. The latest release observed was:

- CopilotKit: `v1.57.3`
- Source checked: `https://github.com/CopilotKit/CopilotKit/releases`

The local demo packages were upgraded to the matching release line:

```json
{
  "@copilotkit/a2ui-renderer": "^1.57.3",
  "@copilotkit/react-core": "^1.57.3",
  "@copilotkit/react-ui": "^1.57.3",
  "@copilotkit/runtime": "^1.57.3"
}
```

Important clarification: the npm package version is `1.57.3`; the app uses CopilotKit's v2 React export surface from `@copilotkit/react-core/v2`.

Current v2 APIs used in the app:

- `CopilotKitProvider`
- `CopilotChat`
- `useAgentContext`
- `useComponent`
- `useFrontendTool`

Implementation references:

- `src/main.tsx`
- `src/copilotRegistrations.tsx`
- `src/localGreenlightAgent.ts`
- `package.json`

## 3. Use Case Built

The use case is now framed as an agent-native film greenlighting workspace.

Working project:

- Title: `Lunar Drift`
- Genre: science fiction
- Budget shape: hybrid
- Decision flow: run analysis, inspect comparable evidence, approve evidence, approve decision, lock pitch package

The article angle is no longer "Copilot chat next to an app." The stronger framing is:

> A CopilotKit-powered decision room where the assistant has live access to backend analysis state, selected comparable titles, approval gates, and package readiness, and can participate in the workflow through registered context, tools, and generated UI surfaces.

## 4. Backend Integration

The frontend calls the existing Greenlighting Agent backend through the Vite proxy.

Relevant frontend files:

- `src/api.ts`
- `vite.config.ts`
- `src/main.tsx`

The core flow:

1. User clicks `Run Greenlight Analysis`.
2. Frontend calls the backend analyze/report flow.
3. Backend result updates the local `GreenlightState`.
4. The Copilot context receives the updated report state.
5. The UI moves from pre-analysis mode to report-aware review mode.

The backend remains the source of truth for the generated greenlight report signal. The frontend does not fabricate the final report state before the backend run.

Observed runtime states:

- `idle`
- `running`
- `completed`
- `failed`
- `offline`

These are represented in `GreenlightState.backendStatus`.

## 5. Local Copilot Agent Behavior

We added and refined a local AG-UI style agent implementation in:

- `src/localGreenlightAgent.ts`

Key behavior change:

- Before backend analysis completes, the Copilot no longer gives a canned analytical answer.
- If the backend status is not `completed`, it tells the user to run the greenlight analysis first.
- If the backend is running, it says the analysis is still running.
- Once the backend report is available, responses are grounded in the current app state.

Post-analysis intents handled include:

- Report/result summary
- Risks
- Comparables
- Budget
- Release shape
- Approval readiness
- Pitch package readiness

This fixes the earlier issue where typing anything into Copilot produced the same generic answer even before the backend analysis was done.

## 6. CopilotKit Features Showcased

### 6.1 Shared Context

Implemented through:

- `useAgentContext`

File:

- `src/copilotRegistrations.tsx`

The app registers greenlight state so the Copilot can read the live decision context, including:

- Project profile
- Backend status
- Report recommendation
- Confidence
- Comparable titles
- Approval gate status
- Package lock state

UI surface:

- `CopilotKit: context` badge in the decision room.

### 6.2 Declarative / Generative UI

Implemented through:

- `useComponent`

File:

- `src/copilotRegistrations.tsx`

The app registers component schemas for Copilot-controlled display surfaces. The visible Comparable Evidence section is labeled:

- `CopilotKit: generative UI`

This supports the article point that CopilotKit can do more than emit text. It can map agent output/state into structured React UI.

### 6.3 Frontend Tools / App Control

Implemented through:

- `useFrontendTool`

File:

- `src/copilotRegistrations.tsx`

Registered tool-style actions include approval and panel-control behavior. In the UI this is represented around the human approval gate:

- `CopilotKit: tools`

This is the "Copilot can operate the app" part of the demo, distinct from just answering questions.

### 6.4 Open / Local Agent Runtime Path

Implemented through:

- `CopilotKitProvider`
- Local `agents__unsafe_dev_only` runtime fallback
- Optional `runtimeUrl` path when configured

File:

- `src/main.tsx`

Current provider setup:

```tsx
<CopilotKitProvider
  {...(runtimeUrl ? { runtimeUrl } : { agents__unsafe_dev_only: { default: localGreenlightAgent } })}
>
```

This means:

- The demo can run locally with the local Greenlight copilot agent.
- It can later be wired to a hosted runtime/API path by providing a runtime URL.
- The current local setup is suitable for article/demo development but should be documented clearly if published.

### 6.5 A2UI / Decision Snapshot

The decision snapshot panel is labeled:

- `CopilotKit: A2UI`

The current implementation uses the CopilotKit A2UI package as a dependency and presents the decision state as an agent-readable/user-readable panel. The article should be careful not to overclaim a fully dynamic A2UI-generated document if the final version remains primarily state-rendered React.

## 7. UI/UX Changes Made

### 7.1 Workspace-First Layout

The layout was reorganized so the main decision workspace comes first and the Copilot panel sits to the side.

Before:

- The Copilot/chat area visually dominated and the actual workflow felt secondary.

After:

- Decision room is the primary surface.
- Copilot is framed as a report-aware assistant.
- Backend and approval states are visible in the main app.

Primary file:

- `src/main.tsx`

Primary CSS:

- `styles.css`

### 7.2 Copilot Readiness Panel

Added `CopilotReadiness` in:

- `src/main.tsx`

The panel explains state without using article/test-note language in the main UI.

Modes:

- Before backend report: waits for backend analysis.
- After backend report: shows report context loaded, recommendation, confidence, and approval progress.

### 7.3 Approval Status Strip

Added `ApprovalStatusStrip` in:

- `src/main.tsx`

The strip shows progress across:

- Evidence
- Assumptions
- Recommendation
- Package

This was added because the earlier flow had buttons that appeared to do nothing. Now the user can see state changes after approvals.

### 7.4 Approval Button State

Updated:

- `Approve Evidence` -> `Evidence Approved`
- `Approve Decision` -> `Decision Approved`

Buttons now receive a visible selected state.

Relevant code:

- `approveEvidence()`
- `approveDecision()`
- `.secondary-action.selected`

Files:

- `src/main.tsx`
- `styles.css`

### 7.5 Package Lock Sequencing

The pitch package lock now respects approval sequencing.

Current behavior:

- `Lock Pitch Package` is disabled until required approval gates are complete.
- Once locked, the UI reflects the package lock state.

Files:

- `src/main.tsx`

### 7.6 CopilotKit Control Badges

Added visible badges to answer the question: "Other than the chat box, which UI sections are controlled via CopilotKit?"

Badges now appear on:

- Report drawer: `CopilotKit: backend bridge`
- Decision room: `CopilotKit: context`
- Comparable evidence: `CopilotKit: generative UI`
- Decision snapshot: `CopilotKit: A2UI`
- Approval gate: `CopilotKit: tools`

This gives article readers and demo viewers a clearer way to see what CopilotKit is doing beyond chat.

### 7.7 Comparable Evidence Whitespace Fix

The user pointed out excessive whitespace between `Selected titles` and the movie cards.

CSS changes made:

- `.studio-grid` now uses tighter columns and `align-items: start`.
- `.live-panel` uses `align-content: start`.
- `.generative-panel` uses `align-self: start`.
- `.movie-card` no longer forces an unnecessary minimum height.
- `.movie-card button` no longer pushes itself to the bottom with large empty space.

Browser geometry check after fix:

```json
{
  "gapAfterHeading": 14,
  "badgeVisible": true
}
```

This confirms the heading-to-card gap was reduced to roughly `14px`.

## 8. Current User Flow

Recommended demo flow:

1. Open the app at `http://127.0.0.1:5173/`.
2. Start on `Decision Room`.
3. Click `Run Greenlight Analysis`.
4. Wait for backend analysis to complete.
5. Review:
   - Current call
   - Comparable Evidence
   - Decision Snapshot
   - Generated Report Preview
6. Ask Copilot questions after the report is loaded, for example:
   - "What are the key risks?"
   - "Why these comparable titles?"
   - "Is the package ready?"
   - "What should we approve next?"
7. Click `Approve Evidence`.
8. Confirm approval status updates.
9. Click `Approve Decision`.
10. Confirm the package gate becomes ready.
11. Click `Lock Pitch Package`.
12. Use the enabled report/package actions if available.

Important demo principle:

- The Copilot becomes useful after the backend report exists.
- Before that, it should guide the user to run the analysis rather than inventing report conclusions.

## 9. Test and Validation Status

Command run:

```bash
npm test
```

Result:

- Passed.

What `npm test` does:

```bash
node tests/smoke.mjs && npm run build
```

Smoke test confirms:

- Required CopilotKit package hooks/components are present.
- Backend integration points exist.
- Local Greenlight agent file exists and is wired.

Build result:

- TypeScript compile succeeded.
- Vite production build succeeded.

Build warning:

- Vite reported large chunks over `500 kB`.
- This is not currently blocking functionality.
- If this became a production app, code splitting should be considered.

Package manager note:

- `npm install` reported `4 moderate` npm audit issues.
- They were not changed in this session because automatic audit fixes could alter dependency behavior and were outside the requested UI/CopilotKit pass.

## 10. Files Changed or Central to This Session

Primary implementation files:

- `src/main.tsx`
- `src/localGreenlightAgent.ts`
- `src/copilotRegistrations.tsx`
- `styles.css`
- `package.json`
- `package-lock.json`

Supporting files:

- `src/api.ts`
- `src/types.ts`
- `src/data.ts`
- `vite.config.ts`
- `tests/smoke.mjs`

Generated/validation artifacts present in the workspace:

- `greenlight-flow-test.mp4`
- `greenlight-flow-01-start.png`
- `greenlight-flow-02-analysis-complete.png`
- `greenlight-flow-03-approve-evidence.png`
- `greenlight-flow-04-approve-decision.png`
- `greenlight-flow-05-package-locked.png`
- `greenlight-copilot-current.png`

## 11. What Is Working Now

Confirmed working:

- Vite app runs locally at `http://127.0.0.1:5173/`.
- CopilotKit packages are on `1.57.3`.
- v2 React imports are used.
- Local Greenlight copilot agent is wired through `CopilotKitProvider`.
- Backend analysis can drive frontend state.
- Copilot refuses to invent analysis before backend completion.
- Copilot answers become report-aware after backend completion.
- Evidence approval visibly changes button and approval state.
- Decision approval visibly changes button and approval state.
- Package lock is sequenced after approvals.
- Comparable evidence layout is less clunky.
- Main UI labels show which sections correspond to CopilotKit capabilities.
- `npm test` passes.

## 12. Known Limitations / Follow-Up Items

### 12.1 Runtime Story

The app currently supports:

- Local development agent through `agents__unsafe_dev_only`.
- Optional runtime URL path when configured.

Before publishing the article or pushing this into the existing Greenlighting Agent repo, we should decide whether the article presents:

- A local-first CopilotKit demo with existing backend integration.
- A hosted CopilotKit runtime version.
- Both, with local setup first and hosted runtime as the production path.

### 12.2 A2UI Claim Should Stay Precise

The app includes `@copilotkit/a2ui-renderer` and labels the decision snapshot as A2UI. The final article should be precise about what is actually dynamic and what is state-rendered React.

Recommended wording:

- "A2UI-style decision snapshot backed by live agent state"

Avoid overclaiming:

- "The entire report UI is generated dynamically by A2UI"

unless we implement that explicitly.

### 12.3 Production Polish

Potential future improvements:

- Add a hosted Copilot runtime configuration example.
- Add clearer environment setup docs.
- Add Playwright-based browser assertions for the approval flow.
- Add code splitting to reduce Vite chunk warnings.
- Decide whether to move this demo into the existing Greenlighting Agent repo as an `/examples/copilotkit-greenlight` or frontend branch.

## 13. Article-Relevant Technical Narrative

The strongest article narrative is:

1. Start with a real backend workflow: a greenlighting agent that produces a report.
2. Add CopilotKit not as a chat widget, but as an interaction layer over the workflow.
3. Register live app state as agent context.
4. Expose frontend tools so the assistant can help operate approval gates.
5. Render structured recommendation/evidence surfaces instead of only text answers.
6. Keep human-in-the-loop approval explicit.
7. Use the final pitch package lock as the business outcome.

This makes the demo useful, decently complex, and more credible than a basic chatbot example.

## 14. Current Handoff

To run locally:

```bash
npm install
npm run dev
```

To validate:

```bash
npm test
```

Expected app URL:

```text
http://127.0.0.1:5173/
```

If using the existing Greenlighting Agent backend, ensure the backend is running at the URL expected by `vite.config.ts` and `src/api.ts`.

## 15. LLM-Backed Runtime Update

After the initial UI/runtime pass, we added a real local CopilotKit runtime option so the demo can move beyond the browser-only local agent fallback. The runtime supports OpenAI when `OPENAI_API_KEY` is present and Anthropic when `ANTHROPIC_API_KEY` is present.

New files:

- `scripts/copilot-runtime.mjs`
- `.env.example`

Updated files:

- `package.json`
- `README.md`
- `tests/smoke.mjs`
- `src/localGreenlightAgent.ts`

New scripts:

```bash
npm run copilot:runtime
npm run dev:runtime
```

Runtime endpoint:

```text
http://127.0.0.1:4010/api/copilotkit
```

Health endpoint:

```text
http://127.0.0.1:4010/health
```

The runtime registers a default Greenlight agent through `CopilotRuntime` and `copilotRuntimeNodeHttpEndpoint`. The agent reads the current CopilotKit state/context, compacts the greenlight state, and calls the configured LLM provider with the selected model.

Default model if no env model is supplied:

```text
gpt-4o-mini
```

Provider selection:

- `OPENAI_API_KEY` present: use OpenAI.
- `ANTHROPIC_API_KEY` present and OpenAI key absent: use Anthropic.
- Existing Greenlighting Agent `.env` can be loaded explicitly through `GREENLIGHT_ENV_FILE`.

Current validation:

- Runtime script syntax check passed.
- `npm test` passed after adding the runtime checks.
- Runtime server started successfully on `127.0.0.1:4010` when run outside the sandbox.
- Health check returned:

```json
{
  "ok": true,
  "basePath": "/api/copilotkit",
  "provider": "anthropic",
  "model": "claude-sonnet-4-5-20250929",
  "openaiKeyConfigured": false,
  "anthropicKeyConfigured": true
}
```

Direct CopilotKit single-route POST test succeeded against the Anthropic-backed runtime. The runtime emitted AG-UI SSE events including:

- `STATE_SNAPSHOT`
- `RUN_STARTED`
- `TEXT_MESSAGE_START`
- `TEXT_MESSAGE_CONTENT`
- `TEXT_MESSAGE_END`
- `RUN_FINISHED`

The live response correctly refused to invent a risk view before backend analysis and instructed the user to run greenlight analysis first.

To live-test with OpenAI instead:

```bash
cp .env.example .env.local
# edit .env.local and set OPENAI_API_KEY
npm run copilot:runtime
npm run dev:runtime
```

Then open:

```text
http://127.0.0.1:5173/
```

or another Vite port if `5173` is already in use.
