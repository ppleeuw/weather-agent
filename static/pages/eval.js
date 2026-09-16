// eval.js: the Eval page. One row per model with the pass rate of each
// layer, a Run button per row and one Run all button, a progress line while
// a run is going, and the failures of the latest runs under the table.
//
// The page polls GET /api/eval every 2 s while a run is in progress. It stops
// when the run is done or when the page is left, which it notices because its
// heading is no longer in the document.

import { getEval, getSettings, runEval } from "../api.js";
import { el, errorBox, table } from "../dom.js";
import { formatCost, formatLatency, formatRate, formatTime } from "../format.js";

const POLL_MS = 2000;
const INTRO =
  "Fifteen golden questions, four checks each: the tools the model called, how it used them, " +
  "whether the answer is grounded in the tool results, and the answer rules. A rate is passed over applicable.";
const HEADERS = ["Model", "Tools", "Usage", "Grounding", "Rules", "Latency", "Cost", ""];

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
    timer: null,
  };
  const toolbar = el("div", "chips");
  toolbar.append(view.runAll);
  view.progress.hidden = true;
  container.append(view.heading, el("p", "muted", INTRO), toolbar, view.progress, view.results, view.failures);
  try {
    const settings = await getSettings();
    view.modelIds = settings.options.understand; // the same four models the Models page offers
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

function resultTable(state) {
  const rows = [];
  for (const modelId of view.modelIds) {
    rows.push(modelRow(modelId, state.latest[modelId], state.running));
  }
  return table(HEADERS, rows);
}

function modelRow(modelId, latest, running) {
  const run = runButton("Run", modelId, "button-secondary");
  run.disabled = running;
  if (!latest) {
    return [twoLineCell(modelId, "not run yet"), "", "", "", "", "", "", run];
  }
  const summary = latest.summary;
  return [
    twoLineCell(latest.label, modelId + " · " + formatTime(latest.finished_at)),
    figure(formatRate(summary.tools)),
    figure(formatRate(summary.usage)),
    figure(formatRate(summary.grounding)),
    figure(formatRate(summary.rules)),
    figure(formatLatency(summary.mean_latency_ms)),
    figure(formatCost(summary.mean_cost_usd)),
    run,
  ];
}

// A figure that must not wrap, so the model column gets the spare width.
function figure(text) {
  return el("span", "nowrap", text);
}

// A cell with a title and a small muted line under it.
function twoLineCell(title, subtitle) {
  const cell = el("div");
  cell.append(el("div", "", title), el("div", "small muted", subtitle));
  return cell;
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
      rows.push([summary.label || modelId, twoLineCell(failure.item, failure.question), failure.layer, failure.reason]);
    }
  }
  if (Object.keys(latest).length === 0) {
    block.append(el("p", "muted", "No eval run yet. Press Run all to test every model against the golden set."));
  } else if (rows.length === 0) {
    block.append(el("p", "muted", "No failures in the latest runs."));
  } else {
    block.append(el("p", "", "Failures in the latest run per model"), table(["Model", "Item", "Layer", "Reason"], rows));
  }
  return block;
}
