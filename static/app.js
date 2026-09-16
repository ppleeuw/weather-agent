// app.js: the page's behaviour, in three parts: the ask flow (question in,
// answer out), the health dot with its card, and the footer version.
// The settings modal lives in settings.js; this file only starts it. The
// figures of a request (model, latency, cost) live on the Trace page.

import { ask, getHealth } from "./api.js";
import { badge, el } from "./dom.js";
import { formatLatency, formatTime } from "./format.js";
import { initSettings } from "./settings.js";

const HEALTH_INTERVAL_MS = 60 * 1000; // the server caches its checks for 60 s, so polling faster gains nothing
const DOT_STATES = ["ok", "degraded", "down"]; // the classes styles.css knows; anything else leaves the dot grey

// Every element the script touches, looked up once. A wrong id fails on load, not on click.
const form = document.getElementById("ask-form");
const input = document.getElementById("question");
const result = document.getElementById("result");
const spinner = document.getElementById("spinner");
const answerText = document.getElementById("answer");
const suggestionChips = document.getElementById("suggestions");
const errorText = document.getElementById("error");
const emptyState = document.getElementById("empty");
const versionText = document.getElementById("version");
const healthDot = document.getElementById("health-dot");
const healthCard = document.getElementById("health-card");

let inFlight = false; // one question at a time; the input stays enabled meanwhile

// ---------- Ask flow ----------

function onSubmit(event) {
  event.preventDefault(); // the form must not reload the page
  const question = input.value.trim();
  if (inFlight || question === "") {
    return;
  }
  askQuestion(question);
}

async function askQuestion(question) {
  inFlight = true;
  showLoading();
  try {
    const body = await ask(question);
    renderResponse(body);
  } catch (error) {
    // The server was unreachable or answered a 4xx or 5xx: say what failed and what to do.
    renderError("Could not get an answer: " + error.message + ". Check that the server is running and try again.");
  } finally {
    spinner.hidden = true;
    inFlight = false;
  }
}

function showLoading() {
  emptyState.hidden = true;
  result.hidden = false;
  spinner.hidden = false;
  answerText.textContent = "";
  suggestionChips.replaceChildren();
  errorText.hidden = true;
}

function renderResponse(body) {
  if (!body.ok) {
    renderError(body.error || "The request failed. Please try again.");
    return;
  }
  answerText.textContent = body.answer;
  renderSuggestions(body.suggestions || []);
}

// Suggestions are complete questions, so a chip fills the input and submits.
function renderSuggestions(suggestions) {
  suggestionChips.replaceChildren();
  for (const text of suggestions) {
    const chip = el("button", "button-secondary", text);
    chip.type = "button";
    chip.addEventListener("click", () => submitQuestion(text));
    suggestionChips.append(chip);
  }
}

function submitQuestion(text) {
  input.value = text;
  input.focus();
  form.requestSubmit(); // fires the submit event, so typed and clicked questions share one path
}

function renderError(message) {
  errorText.textContent = message;
  errorText.hidden = false;
}

// ---------- Health dot and card ----------

async function refreshHealth() {
  try {
    const report = await getHealth();
    renderHealth(report);
    versionText.textContent = "Weather Agent v" + report.version;
  } catch (error) {
    // The server itself is unreachable: that is as down as it gets.
    setDotState("down");
    healthCard.replaceChildren(el("div", "", "Health check failed: " + error.message));
  }
}

function renderHealth(report) {
  setDotState(report.status);
  healthCard.replaceChildren(el("div", "muted", statusLine(report)));
  for (const check of report.checks) {
    healthCard.append(checkRow(check));
  }
}

// The state class goes on the button; the inner span.dot takes its colour from it (see styles.css).
function setDotState(status) {
  healthDot.classList.remove(...DOT_STATES);
  if (DOT_STATES.includes(status)) {
    healthDot.classList.add(status);
  }
}

function statusLine(report) {
  const mode = report.offline ? "offline" : "live";
  return "Status " + report.status + " · " + mode + " · checked " + formatTime(report.checked_at);
}

// One row per check: name, ok or fail badge, then latency and detail in muted text.
function checkRow(check) {
  const row = el("div", "row");
  const figures = formatLatency(check.latency_ms) + " · " + check.detail;
  row.append(el("span", "", check.name), " ", badge(check.ok), " ", el("span", "muted", figures));
  return row;
}

function setHealthCardOpen(open) {
  healthCard.hidden = !open;
  healthDot.setAttribute("aria-expanded", String(open));
}

function onHealthDotClick() {
  setHealthCardOpen(healthCard.hidden);
}

// A click anywhere outside the card closes it; a click on the dot is handled above.
function onDocumentClick(event) {
  if (healthCard.hidden || healthDot.contains(event.target) || healthCard.contains(event.target)) {
    return;
  }
  setHealthCardOpen(false);
}

// ---------- Start ----------

function start() {
  form.addEventListener("submit", onSubmit);
  for (const button of emptyState.querySelectorAll("[data-question]")) {
    button.addEventListener("click", () => submitQuestion(button.dataset.question));
  }
  healthDot.addEventListener("click", onHealthDotClick);
  document.addEventListener("click", onDocumentClick);
  initSettings();
  refreshHealth();
  setInterval(refreshHealth, HEALTH_INTERVAL_MS);
}

start();
