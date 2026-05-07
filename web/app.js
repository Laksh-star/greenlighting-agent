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
const batchCsv = document.querySelector("#batch-csv");
const loadBatchSample = document.querySelector("#load-batch-sample");
const runBatch = document.querySelector("#run-batch");
const batchStatus = document.querySelector("#batch-status");
const batchDownloads = document.querySelector("#batch-downloads");
const batchCsvDownload = document.querySelector("#batch-csv-download");
const batchJsonDownload = document.querySelector("#batch-json-download");
const comparisonTable = document.querySelector("#comparison-table");
const comparableQuery = document.querySelector("#comparable-query");
const searchComparables = document.querySelector("#search-comparables");
const comparableSearchStatus = document.querySelector("#comparable-search-status");
const selectedComparables = document.querySelector("#selected-comparables");
const comparableResults = document.querySelector("#comparable-results");
const comparableSource = document.querySelector("#comparable-source");
const privateDatasetSelect = document.querySelector("#private-dataset-select");
const privateDatasetName = document.querySelector("#private-dataset-name");
const privateDatasetCsv = document.querySelector("#private-dataset-csv");
const loadPrivateSample = document.querySelector("#load-private-sample");
const savePrivateDataset = document.querySelector("#save-private-dataset");
const privateDatasetStatus = document.querySelector("#private-dataset-status");

let currentJobId = "";
let currentBatchJobId = "";
let eventSource = null;
let batchEventSource = null;
let completedAgents = new Set();
let selectedComparableTitles = [];

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
  selectedComparableTitles = parseComparableInput(sample.comparables);
  renderSelectedComparables();
  document.querySelector("#demo-mode").checked = true;
});

loadBatchSample.addEventListener("click", async () => {
  const response = await fetch("/api/sample-batch");
  const sample = await response.json();
  batchCsv.value = sample.csv_text;
});

searchComparables.addEventListener("click", async () => {
  await runComparableSearch();
});

loadPrivateSample.addEventListener("click", async () => {
  const response = await fetch("/api/private-datasets/sample");
  const sample = await response.json();
  privateDatasetCsv.value = sample.csv_text;
  privateDatasetStatus.textContent = "Sample private dataset loaded.";
});

savePrivateDataset.addEventListener("click", async () => {
  await saveCurrentPrivateDataset();
});

comparableQuery.addEventListener("keydown", async (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    await runComparableSearch();
  }
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
    demo_mode: document.querySelector("#demo-mode").checked,
    comparable_source: comparableSource.value,
    private_dataset_id: privateDatasetSelect.value
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

runBatch.addEventListener("click", async () => {
  if (!batchCsv.value.trim()) {
    batchStatus.textContent = "Add CSV rows before running batch";
    return;
  }
  resetBatchState();
  runBatch.disabled = true;
  batchStatus.textContent = "Starting batch";

  try {
    const response = await fetch("/api/batch-analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        csv_text: batchCsv.value,
        demo_mode: document.querySelector("#demo-mode").checked
      })
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const body = await response.json();
    currentBatchJobId = body.job_id;
    connectBatchEvents(body.events_url);
  } catch (error) {
    batchStatus.textContent = "Batch failed";
    comparisonTable.innerHTML = `<p class="placeholder">${escapeHtml(error.message)}</p>`;
    runBatch.disabled = false;
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

function connectBatchEvents(eventsUrl) {
  if (batchEventSource) {
    batchEventSource.close();
  }
  batchEventSource = new EventSource(eventsUrl);
  batchEventSource.onmessage = async (message) => {
    const event = JSON.parse(message.data);
    renderBatchEvent(event);
    if (event.stage === "job" && event.status === "completed") {
      batchEventSource.close();
      await finishBatchJob();
    }
    if (event.stage === "job" && event.status === "failed") {
      batchEventSource.close();
      batchStatus.textContent = "Batch failed";
      runBatch.disabled = false;
    }
  };
  batchEventSource.onerror = () => {
    batchEventSource.close();
    batchStatus.textContent = "Batch stream disconnected";
    runBatch.disabled = false;
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

async function finishBatchJob() {
  const response = await fetch(`/api/jobs/${currentBatchJobId}`);
  const job = await response.json();
  batchStatus.textContent = `Completed ${job.rows.length} projects`;
  runBatch.disabled = false;
  batchCsvDownload.href = job.download_batch_csv_url;
  batchJsonDownload.href = job.download_batch_json_url;
  batchDownloads.classList.remove("hidden");
  comparisonTable.innerHTML = renderComparisonTable(job.rows);
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

function renderBatchEvent(event) {
  if (event.stage === "batch_project") {
    batchStatus.textContent = `${event.name} ${event.status}`;
  }
  if (event.stage === "job" && event.status === "started") {
    batchStatus.textContent = `Running ${event.total || ""} projects`;
  }
  if (event.stage === "job" && event.status === "completed") {
    batchStatus.textContent = "Batch complete";
  }
}

function renderComparisonTable(rows) {
  if (!rows.length) {
    return `<p class="placeholder">No comparison rows returned.</p>`;
  }
  const tableRows = rows.map((row) => `
    <tr>
      <td>${escapeHtml(row.project_name)}</td>
      <td><span class="mini-pill ${recommendationClass(row.recommendation)}">${escapeHtml(row.recommendation)}</span></td>
      <td>${Math.round((Number(row.confidence) || 0) * 100)}%</td>
      <td>${escapeHtml(row.moderate_roi || "n/a")}</td>
      <td>${escapeHtml(row.risk_level || "n/a")}</td>
      <td>${escapeHtml(row.overall_risk_score || "n/a")}</td>
      <td><a href="/api/output?path=${encodeURIComponent(row.report_path)}">Report</a></td>
    </tr>
  `).join("");
  return `
    <table>
      <thead>
        <tr>
          <th>Project</th>
          <th>Recommendation</th>
          <th>Confidence</th>
          <th>ROI</th>
          <th>Risk</th>
          <th>Risk Score</th>
          <th>Output</th>
        </tr>
      </thead>
      <tbody>${tableRows}</tbody>
    </table>
  `;
}

async function runComparableSearch() {
  const query = comparableQuery.value.trim();
  if (query.length < 2) {
    comparableSearchStatus.textContent = "Enter at least 2 characters.";
    return;
  }
  searchComparables.disabled = true;
  comparableSearchStatus.textContent = "Searching comparables";
  comparableResults.innerHTML = "";

  try {
    const params = new URLSearchParams({
      q: query,
      source: comparableSource.value,
      dataset_id: privateDatasetSelect.value
    });
    const response = await fetch(`/api/comparables/search?${params.toString()}`);
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const payload = await response.json();
    comparableSearchStatus.textContent = payload.warning || `${payload.results.length} results from ${payload.source}`;
    comparableResults.innerHTML = renderComparableCards(payload.results);
  } catch (error) {
    comparableSearchStatus.textContent = "Comparable search failed";
    comparableResults.innerHTML = `<p class="placeholder">${escapeHtml(error.message)}</p>`;
  } finally {
    searchComparables.disabled = false;
  }
}

async function saveCurrentPrivateDataset() {
  if (!privateDatasetCsv.value.trim()) {
    privateDatasetStatus.textContent = "Paste dataset CSV before saving.";
    return;
  }
  savePrivateDataset.disabled = true;
  privateDatasetStatus.textContent = "Saving private dataset";
  try {
    const response = await fetch("/api/private-datasets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: privateDatasetName.value || "Studio Dataset",
        csv_text: privateDatasetCsv.value
      })
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const payload = await response.json();
    privateDatasetStatus.textContent = `Saved ${payload.dataset.row_count} rows as ${payload.dataset.name}`;
    await loadPrivateDatasets(payload.dataset.id);
    comparableSource.value = "private";
  } catch (error) {
    privateDatasetStatus.textContent = `Save failed: ${error.message}`;
  } finally {
    savePrivateDataset.disabled = false;
  }
}

async function loadPrivateDatasets(selectedId = "") {
  const response = await fetch("/api/private-datasets");
  const payload = await response.json();
  privateDatasetSelect.innerHTML = `<option value="">All local datasets</option>`;
  for (const dataset of payload.datasets) {
    const option = document.createElement("option");
    option.value = dataset.id;
    option.textContent = `${dataset.name} (${dataset.row_count})`;
    privateDatasetSelect.appendChild(option);
  }
  if (selectedId) {
    privateDatasetSelect.value = selectedId;
  }
}

function renderComparableCards(results) {
  if (!results.length) {
    return `<p class="placeholder">No comparable titles found.</p>`;
  }
  return results.map((item) => {
    const selected = selectedComparableTitles.includes(item.title);
    return `
      <article class="comparable-card">
        ${item.poster_url ? `<img src="${escapeHtml(item.poster_url)}" alt="${escapeHtml(item.title)} poster">` : `<div class="poster-placeholder">No poster</div>`}
        <div>
          <h3>${escapeHtml(item.title)}</h3>
          <p>${escapeHtml(item.year)} · Rating ${formatNumber(item.rating)} · Popularity ${formatNumber(item.popularity)}</p>
          <p>${formatMoney(item.budget)} budget · ${formatMoney(item.revenue)} revenue</p>
          <p>${escapeHtml(truncate(item.overview || item.source || "", 120))}</p>
          <button type="button" class="select-comparable ${selected ? "selected" : ""}" data-title="${escapeHtml(item.title)}">${selected ? "Selected" : "Add"}</button>
        </div>
      </article>
    `;
  }).join("");
}

comparableResults.addEventListener("click", (event) => {
  const button = event.target.closest(".select-comparable");
  if (!button) {
    return;
  }
  const title = button.dataset.title;
  if (!title) {
    return;
  }
  if (selectedComparableTitles.includes(title)) {
    selectedComparableTitles = selectedComparableTitles.filter((item) => item !== title);
  } else if (selectedComparableTitles.length < 5) {
    selectedComparableTitles.push(title);
  } else {
    comparableSearchStatus.textContent = "Use up to 5 comparables for a focused analysis.";
  }
  syncComparablesInput();
  renderSelectedComparables();
  button.textContent = selectedComparableTitles.includes(title) ? "Selected" : "Add";
  button.classList.toggle("selected", selectedComparableTitles.includes(title));
});

function syncComparablesInput() {
  setValue("comparables", selectedComparableTitles.join(", "));
}

function renderSelectedComparables() {
  selectedComparables.innerHTML = selectedComparableTitles.map((title) => `
    <button type="button" class="selected-chip" data-title="${escapeHtml(title)}">${escapeHtml(title)} ×</button>
  `).join("");
}

selectedComparables.addEventListener("click", (event) => {
  const chip = event.target.closest(".selected-chip");
  if (!chip) {
    return;
  }
  selectedComparableTitles = selectedComparableTitles.filter((title) => title !== chip.dataset.title);
  syncComparablesInput();
  renderSelectedComparables();
  if (comparableResults.innerHTML) {
    runComparableSearch();
  }
});

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

function resetBatchState() {
  if (batchEventSource) {
    batchEventSource.close();
  }
  currentBatchJobId = "";
  batchDownloads.classList.add("hidden");
  comparisonTable.innerHTML = `<p class="placeholder">Batch is running.</p>`;
}

function recommendationClass(recommendation) {
  if (recommendation === "GO") {
    return "go";
  }
  if (recommendation === "NO-GO") {
    return "no-go";
  }
  return "warn";
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

function parseComparableInput(text) {
  return text.split(",").map((item) => item.trim()).filter(Boolean);
}

function formatMoney(amount) {
  const number = Number(amount) || 0;
  if (!number) {
    return "n/a";
  }
  if (number >= 1000000000) {
    return `$${(number / 1000000000).toFixed(1)}B`;
  }
  if (number >= 1000000) {
    return `$${(number / 1000000).toFixed(1)}M`;
  }
  return `$${number.toLocaleString()}`;
}

function formatNumber(valueToFormat) {
  return (Number(valueToFormat) || 0).toFixed(1);
}

function truncate(text, maxLength) {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 3)}...`;
}

sampleButton.click();
loadBatchSample.click();
loadPrivateDatasets();
