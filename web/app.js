const form = document.querySelector("#analysis-form");
const runButton = document.querySelector("#run-button");
const sampleButton = document.querySelector("#sample-button");
const refreshButton = document.querySelector("#refresh-report");
const eventList = document.querySelector("#event-list");
const jobStatus = document.querySelector("#job-status");
const progressFill = document.querySelector("#progress-fill");
const recommendationPill = document.querySelector("#recommendation-pill");
const reportPreview = document.querySelector("#report-preview");
const downloads = document.querySelector("#download-actions");
const markdownDownload = document.querySelector("#markdown-download");
const jsonDownload = document.querySelector("#json-download");

let currentJobId = "";
let eventSource = null;
let completedAgents = new Set();

const agentLabels = {
  market_research: "Market research",
  financial_model: "Financial model",
  risk_analysis: "Risk analysis",
  audience_intel: "Audience intelligence",
  competitive: "Competitive analysis",
  creative: "Creative assessment",
  master_orchestrator: "Master synthesis",
  analysis: "Analysis"
};

sampleButton.addEventListener("click", async () => {
  const response = await fetch("/api/sample");
  const sample = await response.json();
  setValue("description", sample.description);
  setValue("budget", sample.budget);
  setValue("genre", sample.genre);
  setValue("platform", sample.platform);
  setValue("target-audience", sample.target_audience);
  setValue("comparables", sample.comparables);
  document.querySelector("#demo-mode").checked = true;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetRunState();
  runButton.disabled = true;
  jobStatus.textContent = "Starting";

  const payload = {
    description: value("description"),
    budget: Number(value("budget") || 0),
    genre: value("genre") || "Unknown",
    platform: value("platform") || "theatrical",
    comparables: value("comparables"),
    target_audience: value("target-audience") || "general",
    demo_mode: document.querySelector("#demo-mode").checked
  };

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const body = await response.json();
    currentJobId = body.job_id;
    connectEvents(body.events_url);
  } catch (error) {
    jobStatus.textContent = "Failed";
    addEvent("Request failed", error.message);
    runButton.disabled = false;
  }
});

refreshButton.addEventListener("click", async () => {
  if (currentJobId) {
    await loadReport(currentJobId);
  }
});

function connectEvents(eventsUrl) {
  if (eventSource) {
    eventSource.close();
  }
  eventSource = new EventSource(eventsUrl);
  eventSource.onmessage = async (message) => {
    const event = JSON.parse(message.data);
    renderEvent(event);
    if (event.stage === "job" && event.status === "completed") {
      eventSource.close();
      await finishJob();
    }
    if (event.stage === "job" && event.status === "failed") {
      eventSource.close();
      jobStatus.textContent = "Failed";
      runButton.disabled = false;
    }
  };
  eventSource.onerror = () => {
    eventSource.close();
    jobStatus.textContent = "Stream disconnected";
    runButton.disabled = false;
  };
}

async function finishJob() {
  const response = await fetch(`/api/jobs/${currentJobId}`);
  const job = await response.json();
  jobStatus.textContent = "Completed";
  runButton.disabled = false;
  refreshButton.disabled = false;
  setRecommendation(job.recommendation, job.confidence);
  markdownDownload.href = job.download_markdown_url;
  jsonDownload.href = job.download_json_url;
  downloads.classList.remove("hidden");
  await loadReport(currentJobId);
}

async function loadReport(jobId) {
  const response = await fetch(`/api/jobs/${jobId}/report`);
  if (!response.ok) {
    reportPreview.innerHTML = `<p class="placeholder">${escapeHtml(await response.text())}</p>`;
    return;
  }
  const markdown = await response.text();
  reportPreview.innerHTML = renderMarkdown(markdown);
}

function renderEvent(event) {
  const label = agentLabels[event.name] || event.name || event.stage;
  const detail = event.status === "completed" ? "Completed" : event.status === "started" ? "Started" : event.status;
  addEvent(label, detail);
  if (event.stage === "agent" && event.status === "completed") {
    completedAgents.add(event.name);
    const total = event.total || 6;
    progressFill.style.width = `${Math.min(100, Math.round((completedAgents.size / total) * 100))}%`;
  }
  if (event.stage === "synthesis" && event.status === "started") {
    jobStatus.textContent = "Synthesizing";
    progressFill.style.width = "96%";
  }
  if (event.stage === "job" && event.status === "completed") {
    progressFill.style.width = "100%";
  }
  if (event.stage === "job" && event.status === "started") {
    jobStatus.textContent = "Running";
  }
}

function addEvent(title, detail) {
  const item = document.createElement("li");
  item.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span>`;
  eventList.prepend(item);
}

function setRecommendation(recommendation, confidence) {
  recommendationPill.textContent = recommendation ? `${recommendation} (${Math.round((confidence || 0) * 100)}%)` : "Complete";
  recommendationPill.className = "pill";
  if (recommendation === "GO") {
    recommendationPill.classList.add("go");
  } else if (recommendation === "NO-GO") {
    recommendationPill.classList.add("no-go");
  } else {
    recommendationPill.classList.add("warn");
  }
}

function resetRunState() {
  if (eventSource) {
    eventSource.close();
  }
  currentJobId = "";
  completedAgents = new Set();
  eventList.innerHTML = "";
  progressFill.style.width = "0%";
  recommendationPill.textContent = "Running";
  recommendationPill.className = "pill";
  downloads.classList.add("hidden");
  refreshButton.disabled = true;
  reportPreview.innerHTML = `<p class="placeholder">Report will appear when the run completes.</p>`;
}

function renderMarkdown(markdown) {
  const lines = markdown.split("\n");
  const html = [];
  let inList = false;
  let inTable = false;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      if (inTable) {
        html.push("</tbody></table>");
        inTable = false;
      }
      continue;
    }

    if (line.startsWith("|") && line.endsWith("|")) {
      const cells = line.slice(1, -1).split("|").map((cell) => cell.trim());
      if (cells.every((cell) => /^:?-{3,}:?$/.test(cell))) {
        continue;
      }
      if (!inTable) {
        html.push("<table><tbody>");
        inTable = true;
      }
      const tag = html[html.length - 1] === "<table><tbody>" ? "th" : "td";
      html.push(`<tr>${cells.map((cell) => `<${tag}>${inlineMarkdown(cell)}</${tag}>`).join("")}</tr>`);
      continue;
    }

    if (inTable) {
      html.push("</tbody></table>");
      inTable = false;
    }

    if (line.startsWith("- ")) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${inlineMarkdown(line.slice(2))}</li>`);
      continue;
    }

    if (inList) {
      html.push("</ul>");
      inList = false;
    }

    if (line.startsWith("### ")) {
      html.push(`<h3>${inlineMarkdown(line.slice(4))}</h3>`);
    } else if (line.startsWith("## ")) {
      html.push(`<h2>${inlineMarkdown(line.slice(3))}</h2>`);
    } else if (line.startsWith("# ")) {
      html.push(`<h1>${inlineMarkdown(line.slice(2))}</h1>`);
    } else if (line === "---") {
      html.push("<hr>");
    } else {
      html.push(`<p>${inlineMarkdown(line)}</p>`);
    }
  }

  if (inList) {
    html.push("</ul>");
  }
  if (inTable) {
    html.push("</tbody></table>");
  }
  return html.join("");
}

function inlineMarkdown(text) {
  return escapeHtml(text).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/\*(.*?)\*/g, "<em>$1</em>");
}

function escapeHtml(valueToEscape) {
  return String(valueToEscape)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function value(id) {
  return document.querySelector(`#${id}`).value.trim();
}

function setValue(id, nextValue) {
  document.querySelector(`#${id}`).value = nextValue || "";
}

sampleButton.click();
