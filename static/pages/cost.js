// cost.js: the Cost page. Where every dollar figure comes from: the list
// prices with their source, the cost of the last request per step, the
// session total, and the total of the latest eval run per model.

import { getCost } from "../api.js";
import { el, errorBox, externalLink, table } from "../dom.js";
import { formatCost, formatPrice, formatTokens } from "../format.js";

export async function render(container) {
  const heading = el("h3", "heading", "Cost");
  container.append(heading);
  try {
    const data = await getCost();
    if (!heading.isConnected) {
      return; // the user moved to another page while the data was loading
    }
    container.append(priceSection(data), lastRequestSection(data.last_request));
    container.append(sessionLine(data.session_total_usd), lastEvalSection(data.last_eval));
  } catch (error) {
    if (heading.isConnected) {
      container.append(errorBox("Could not load the cost data: " + error.message));
    }
  }
}

// A section is a one-line title and its content, kept together in one block.
function section(title, content) {
  const block = el("div", "stack");
  block.append(el("p", "", title), content);
  return block;
}

function priceSection(data) {
  const rows = [];
  for (const price of data.prices) {
    const source = externalLink(price.source, hostOf(price.source));
    rows.push([price.model, price.label, formatPrice(price.input_usd_per_mtok), formatPrice(price.output_usd_per_mtok), source]);
  }
  const title = "List prices in USD per million tokens, checked on " + data.checked_on;
  return section(title, table(["Model", "Label", "Input", "Output", "Source"], rows));
}

// "https://mistral.ai/pricing/api" shows as "mistral.ai"; a string that is not a URL shows as it is.
function hostOf(url) {
  try {
    return new URL(url).host;
  } catch (_error) {
    return String(url);
  }
}

function lastRequestSection(last) {
  if (!last) {
    return section("Last request", el("p", "muted", "No request yet."));
  }
  const rows = [];
  for (const step of last.steps) {
    rows.push([step.name, step.handler || "none", formatTokens(step.input_tokens, step.output_tokens), formatCost(step.cost_usd)]);
  }
  rows.push(["Total", "", "", formatCost(last.cost_usd)]);
  return section("Last request: " + last.question, table(["Step", "Handler", "Tokens", "Cost"], rows));
}

function sessionLine(total) {
  return el("p", "", "Session total since the server started: " + formatCost(total));
}

function lastEvalSection(lastEval) {
  if (!lastEval) {
    return section("Last eval run per model", el("p", "muted", "No eval run yet."));
  }
  const rows = [];
  for (const modelId of Object.keys(lastEval)) {
    rows.push([modelId, formatCost(lastEval[modelId])]);
  }
  return section("Last eval run per model", table(["Model", "Total cost"], rows));
}
