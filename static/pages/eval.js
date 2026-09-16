// eval.js: the Eval page. One column per model, one row per layer with its
// pass rate, then mean latency, mean cost, the time of the last run and a Run
// button per model, plus one Run all button, a progress line while a run is
// going, and the failures of the latest runs under the table.
//
// The page polls GET /api/eval every 2 s while a run is in progress. It stops
// when the run is done or when the page is left, which it notices because its
// heading is no longer in the document.

import { getCost, getEval, getSettings, runEval } from "../api.js";
import { el, errorBox, table } from "../dom.js";
import { formatCost, formatLatency, formatRate, formatTime } from "../format.js";

const POLL_MS = 2000;
const INTRO =
  "Fifteen golden questions, four checks each: the tools the model called, how it used them, " +
  "whether the answer is grounded in the tool results, and the answer rules. A rate is passed over applicable.";
// The four pass-rate layers, in the order the eval checks them.
const LAYERS = [
  { key: "tools", label: "Tools: which tools the model called" },
  { key: "usage", label: "Usage: place, date, block" },
  { key: "grounding", label: "Grounding: numbers in the tool results" },
  { key: "rules", label: "Rules: what the answer must contain" },
];

// The elements of the page that is on screen. A new render replaces them all.
let view = null;

export async function render(container) {
  if (view) {
    clearTimeout(view.timer); // a poll scheduled by the previous visit must not run twice
  }
  view = {
    heading: el("h3", "heading", "Eval"),
    runAll: runButton("Run all", "all", "button-primary"),
    progress: el("p", "small muted"),
    results: el("div"),
    failures: el("div"),
    modelIds: [],
    labels: {}, // model id to label, from the price table
    timer: null,
  };
  const toolbar = el("div", "chips");
  toolbar.append(view.runAll);
  view.progress.hidden = true;
  container.append(view.heading, el("p", "muted", INTRO), toolbar, view.progress, view.results, view.failures);
  try {
    const settings = await getSettings();
    view.modelIds = settings.options.understand; // the same four models the Models page offers
    const cost = await getCost();
    for (const price of cost.prices) {
      view.labels[price.model] = price.label;
    }
  } catch (error) {
    view.results.replaceChildren(errorBox("Could not load the model list: " + error.message));
    return;
  }
  refresh();
}

async function refresh() {
  if (!view.heading.isConnected) {
    return; // the page was left; this ends the polling chain
  }
  try {
    const state = await getEval();
    showState(state);
    if (state.running) {
      clearTimeout(view.timer); // one pending poll at a time, whatever started this one
      view.timer = setTimeout(refresh, POLL_MS);
    }
  } catch (error) {
    view.results.replaceChildren(errorBox("Could not load the eval results: " + error.message));
  }
}

function showState(state) {
  view.latest = state.latest;
  view.runAll.disabled = state.running;
  view.progress.hidden = !state.running;
  view.progress.textContent = progressText(state);
  view.results.replaceChildren(resultTable(state));
  view.failures.replaceChildren(failuresBlock(state.latest));
}

function progressText(state) {
  if (!state.running) {
    return "";
  }
  const progress = state.progress;
  return "Running " + progress.model + ": " + progress.done + " of " + progress.total + " questions done.";
}

// Models across, layers down: four models compare best side by side.
function resultTable(state) {
  const headers = [""];
  for (const modelId of view.modelIds) {
    headers.push(view.labels[modelId] || modelId);
  }
  const rows = [perModel("Model id", (modelId) => el("span", "small muted", modelId))];
  for (const layer of LAYERS) {
    rows.push(perModel(layer.label, (modelId, latest) => latest ? formatRate(latest.summary[layer.key]) : "not run yet"));
  }
  rows.push(perModel("Mean latency", (modelId, latest) => latest ? formatLatency(latest.summary.mean_latency_ms) : ""));
  rows.push(perModel("Mean cost per question", (modelId, latest) => latest ? formatCost(latest.summary.mean_cost_usd) : ""));
  rows.push(perModel("Last run", (modelId, latest) => latest ? el("span", "small muted", formatTime(latest.finished_at)) : ""));
  rows.push(perModel("", (modelId) => runButtonFor(modelId, state.running)));
  return table(headers, rows);
}

// One table row: the row title, then one cell per model built by cellFor(modelId, latest).
function perModel(title, cellFor) {
  const row = [title];
  for (const modelId of view.modelIds) {
    row.push(cellFor(modelId, view.latest[modelId]));
  }
  return row;
}

function runButtonFor(modelId, running) {
  const run = runButton("Run", modelId, "button-secondary");
  run.disabled = running;
  return run;
}

function runButton(text, model, className) {
  const button = el("button", className, text);
  button.type = "button";
  button.addEventListener("click", () => startRun(model));
  return button;
}

async function startRun(model) {
  view.progress.hidden = false;
  view.progress.textContent = "Starting…";
  try {
    await runEval(model);
  } catch (error) {
    view.progress.textContent = error.message; // for example "An eval run is already in progress."
    return;
  }
  refresh(); // the server marks the run as running before it answers, so this poll sees it
}

// Every failure of the latest run per model, or one line saying there are none.
function failuresBlock(latest) {
  const block = el("div");
  const rows = [];
  for (const modelId of Object.keys(latest)) {
    const summary = latest[modelId];
    for (const failure of summary.failures || []) {
      rows.push([summary.label || modelId, String(failure.item) + ". " + failure.question, failure.layer, failure.reason]);
    }
  }
  if (Object.keys(latest).length === 0) {
    block.append(el("p", "muted", "No eval run yet. Press Run all to test every model against the golden set."));
  } else if (rows.length === 0) {
    block.append(el("p", "muted", "No failures in the latest runs."));
  } else {
    // Five rows show; the rest scroll inside the box, so a long list never pushes the page down.
    const scroll = el("div", "scroll-box");
    scroll.append(table(["Model", "Item", "Layer", "Reason"], rows));
    block.append(el("p", "", "Failures in the latest run per model"), scroll);
  }
  return block;
}
