// suitability.js: which model fits which step, from the latest eval results.
// The table is live: it reads the saved runs. The assessment text was written
// from the runs of 16 September 2026 and says so.

import { getCost, getEval } from "../api.js";
import { el, errorBox, table } from "../dom.js";
import { formatCost, formatLatency, formatRate } from "../format.js";

const LAYERS = ["tools", "usage", "grounding", "rules"];

// Written from the eval of 16 September 2026; see the Eval page for the current numbers.
const ASSESSMENT = [
  {
    title: "What the four layers measure",
    lines: [
      "Tools and usage judge the understand step: did the model call both tools, name the right place, keep the user's time words, and ask for the right block of data. Grounding and rules judge the answer step: are the numbers real, is the sentence in the asked shape and language.",
      "Fifteen questions is a small set. A single miss moves a rate by seven points, so read the table as a ranking, not as a measurement to two decimals.",
    ],
  },
  {
    title: "Mistral Medium 3.5",
    lines: [
      "15 of 15 on every layer, about 1.4 s per question, about $0.002 per question. It understood the ambiguous Springfield, the past date, the Dutch question and the afternoon window. This is the default for both model steps.",
    ],
  },
  {
    title: "Claude Sonnet 5",
    lines: [
      "15 of 15 on every layer, about 5.5 s per question, about $0.005 per question: the most expensive and the slowest of the four, because it thinks before it answers even at low effort. Its first run answered seven English questions in German; a rewrite of the answer prompt fixed that, and the eval gained an English rule so it cannot happen unseen again. Suited to the understand step when accuracy matters more than speed; too slow for a chat-like feel.",
    ],
  },
  {
    title: "Claude Haiku 4.5",
    lines: [
      "14 of 15 on tools, usage and rules, about 2.4 s and $0.002 per question. It answered the ambiguous Springfield in prose instead of calling a tool, so the app could not offer the three suggestions. Its first run also lost Utrecht by sending the country as Netherlands, which exposed a code bug in the country filter, now fixed. A fair choice for the answer step; for the understand step Mistral Medium is both more accurate and cheaper.",
    ],
  },
  {
    title: "Mistral Small 4",
    lines: [
      "15 of 15 on tools and rules, 14 of 15 on usage, about 2 s and $0.0002 per question: ten times cheaper than the next model. Its one miss dropped the afternoon window from the London question, so the answer covered the whole day. A strong choice for the answer step, where phrasing given facts is enough; for the understand step its one lapse in reading time words is the risk.",
    ],
  },
  {
    title: "Recommendation per step",
    lines: [
      "Understand: Mistral Medium 3.5. Perfect score, fast, mid-priced. Claude Sonnet 5 matches the score at three times the cost and four times the latency.",
      "Answer: Mistral Small 4 when cost matters, Mistral Medium 3.5 when one model should do both. Every model grounded every number in every run, so the phrasing step is the safer place to save.",
    ],
  },
];

export async function render(container) {
  const heading = el("h3", "heading", "Model suitability");
  container.append(heading, el("p", "muted", "Pass rates per layer, latency and cost per question from the latest eval run of each model, and what that means for the two model steps."));
  try {
    const [state, cost] = await Promise.all([getEval(), getCost()]);
    if (!heading.isConnected) {
      return;
    }
    const labels = {};
    for (const price of cost.prices) {
      labels[price.model] = price.label;
    }
    container.append(comparison(state.latest, labels));
    for (const entry of ASSESSMENT) {
      container.append(assessmentCard(entry));
    }
  } catch (error) {
    if (heading.isConnected) {
      container.append(errorBox("Could not load the eval results: " + error.message));
    }
  }
}

// One row per model that has a run: the four layers, then latency and cost.
function comparison(latest, labels) {
  const rows = [];
  for (const modelId of Object.keys(latest)) {
    const summary = latest[modelId].summary;
    const cells = [labels[modelId] || modelId];
    for (const layer of LAYERS) {
      cells.push(el("span", "nowrap", formatRate(summary[layer])));
    }
    cells.push(el("span", "nowrap", formatLatency(summary.mean_latency_ms)));
    cells.push(el("span", "nowrap", formatCost(summary.mean_cost_usd)));
    cells.push(el("span", "nowrap", formatCost(summary.mean_cost_usd * 1000)));
    rows.push(cells);
  }
  if (rows.length === 0) {
    return el("p", "muted", "No eval run yet. Run the eval first.");
  }
  return table(["Model", "Tools", "Usage", "Grounding", "Rules", "Latency", "Per question", "Per 1000"], rows);
}

function assessmentCard(entry) {
  const card = el("div", "card stack");
  card.append(el("p", "label", entry.title));
  for (const line of entry.lines) {
    card.append(el("p", "", line));
  }
  return card;
}
