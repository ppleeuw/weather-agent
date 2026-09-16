// eu-ai-act.js: a working assessment of where this app stands under the EU AI
// Act, Regulation (EU) 2024/1689. Written on 16 September 2026 from the
// regulation's text. It is an engineering reading, not legal advice.

import { el } from "../dom.js";

const SECTIONS = [
  {
    title: "What this system is",
    lines: [
      "An AI system in the sense of Article 3(1): software that infers, from a question in natural language, which tools to call and how to phrase an answer. It is built on two general-purpose AI models reached over their APIs, from Mistral and Anthropic.",
      "The app maker is the provider of this downstream system and, when demonstrating it, also its deployer. The providers of the general-purpose models are Mistral and Anthropic.",
    ],
  },
  {
    title: "Risk category",
    lines: [
      "Not prohibited: none of the practices of Article 5 apply to a weather assistant.",
      "Not high-risk: weather information is not among the Annex III areas, and the app is not a safety component of a regulated product under Annex I.",
      "Limited risk with a transparency duty: Article 50(1) requires that people be told they interact with an AI system unless that is obvious. The empty state of the page says so in one sentence, and this page repeats it.",
    ],
  },
  {
    title: "What the model providers owe, and what this app relies on",
    lines: [
      "Article 53 places documentation, a copyright policy and a training-content summary on the providers of general-purpose AI models. This app relies on the model cards and documentation that Mistral and Anthropic publish; the price table and model ids were read from those pages on 16 September 2026.",
      "Whether either model is designated as carrying systemic risk under Article 51 is not checked by this app. To verify with the providers before any commercial use.",
    ],
  },
  {
    title: "Practices this app follows although not required at its risk level",
    lines: [
      "Traceability: every request is recorded end to end, with the system prompt, each model call and its messages, each tool call and result, tokens, latency and cost. The Trace page shows it. This mirrors the record-keeping idea of Article 12 for high-risk systems.",
      "Guardrails: an input length cap, a rate limit, a limit on model calls, a check that every number in the answer exists in the tool results, and a block on answers that repeat the system prompt. Each check is logged, pass or fail.",
      "Evaluation: a golden set of fifteen questions scored by code on four layers, no model as judge, with results per model on the Eval page. This is the accuracy and robustness evidence that Article 15 asks of high-risk systems, kept here as good practice.",
      "Human oversight: the person asking sees the answer, the trace and the health of every dependency, and chooses which model runs each step.",
    ],
  },
  {
    title: "Personal data",
    lines: [
      "The only personal data the app touches is the requester's IP address, used as the key of the rate limit and kept in the trace of the last twenty requests, in memory, never on disk. Questions are recorded for offline replay and in eval reports; the golden questions contain no personal data.",
      "For any deployment beyond a single machine: hash the IP address before storing it, and state the retention of traces and recordings in a privacy notice.",
    ],
  },
  {
    title: "Timeline that applies to this app",
    lines: [
      "Prohibited practices and AI literacy: since 2 February 2025. General-purpose model obligations: since 2 August 2025. Transparency obligations of Article 50: from 2 August 2026, so they apply today.",
      "High-risk obligations phase in from August 2026 and August 2027 and do not apply here. Dates are those of the regulation as adopted; Commission guidance and later amendments should be checked before relying on them.",
    ],
  },
];

export function render(container) {
  container.append(el("h3", "heading", "EU AI Act"));
  container.append(el("p", "muted", "A working assessment of this app under Regulation (EU) 2024/1689, written on 16 September 2026. An engineering reading of the regulation, not legal advice."));
  for (const section of SECTIONS) {
    const block = el("div", "card stack");
    block.append(el("p", "label", section.title));
    for (const line of section.lines) {
      block.append(el("p", "", line));
    }
    container.append(block);
  }
}
