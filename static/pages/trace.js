// trace.js: the Trace page. One request end to end: the totals, every
// guardrail event, then one card per step with its request, raw response
// and result exactly as the server saw them.

import { getTrace } from "../api.js";
import { badge, el, errorBox, table } from "../dom.js";
import { formatCost, formatLatency, formatTime, formatTokens } from "../format.js";

// live is the normal case; replayed is a warning because the data may be stale; skipped is plain muted text.
const SOURCE_CLASSES = { live: "badge ok", replayed: "badge warning", skipped: "small muted" };

export async function render(container, context = {}) {
  const heading = el("h3", "heading", "Trace");
  container.append(heading);
  try {
    const trace = await getTrace(context.traceId);
    if (!heading.isConnected) {
      return; // the user moved to another page while the trace was loading
    }
    container.append(summary(trace), guardrailTable(trace.guardrails));
    for (const step of trace.steps) {
      container.append(stepCard(step));
    }
  } catch (error) {
    if (heading.isConnected) {
      container.append(loadFailure(error));
    }
  }
}

// A 404 means there is nothing to show yet; anything else is a real failure.
function loadFailure(error) {
  if (error.status === 404) {
    const box = el("div", "empty");
    box.append(el("h3", "heading", "Nothing to show yet"), el("p", "muted", error.message + " Ask a question, then come back to see every step of it."));
    return box;
  }
  return errorBox("Could not load the trace: " + error.message);
}

// The question, the answer or error, and the totals in one block.
function summary(trace) {
  const block = el("div", "stack");
  block.append(el("p", "", trace.question));
  if (trace.answer) {
    block.append(el("p", "muted", trace.answer));
  }
  if (trace.error) {
    block.append(errorBox(trace.error));
  }
  block.append(el("p", "small muted", totalsLine(trace)));
  return block;
}

function totalsLine(trace) {
  const totals = trace.totals;
  const figures = [
    "Outcome " + trace.outcome,
    formatLatency(totals.latency_ms),
    formatCost(totals.cost_usd),
    formatTokens(totals.input_tokens, totals.output_tokens),
    totals.model_calls + " model calls",
    "trace " + trace.id,
    "v" + trace.version,
    formatTime(trace.started_at),
  ];
  return figures.join(" · ");
}

function guardrailTable(events) {
  const rows = [];
  for (const event of events) {
    rows.push([event.rule, event.stage, badge(event.outcome === "pass", "pass", "fail"), event.detail]);
  }
  return table(["Rule", "Stage", "Outcome", "Detail"], rows);
}

function stepCard(step) {
  const card = el("div", "card stack");
  card.append(stepHeader(step));
  if (step.error) {
    card.append(errorBox(step.error));
  }
  card.append(jsonDetails("Request", step.request), jsonDetails("Raw response", step.response), jsonDetails("Result", step.result));
  return card;
}

// One line: name, handler, source badge, then latency plus tokens and cost for model steps.
function stepHeader(step) {
  const header = el("div", "row");
  header.append(el("span", "", step.name), el("span", "muted", step.handler || "no handler"));
  header.append(sourceBadge(step.source), el("span", "small muted", stepFigures(step)));
  return header;
}

function stepFigures(step) {
  const figures = [formatLatency(step.latency_ms)];
  if (step.kind === "model") {
    figures.push(formatTokens(step.input_tokens, step.output_tokens), formatCost(step.cost_usd));
  }
  return figures.join(" · ");
}

function sourceBadge(source) {
  return el("span", SOURCE_CLASSES[source] || "small muted", source);
}

// A collapsed block holding one value as indented JSON, so a card stays short until opened.
function jsonDetails(title, value) {
  const block = el("details");
  block.append(el("summary", "small", title), el("pre", "code", asJson(value)));
  return block;
}

function asJson(value) {
  if (value === null || value === undefined) {
    return "none";
  }
  return JSON.stringify(value, null, 2);
}
