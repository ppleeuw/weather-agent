// settings.js: the settings modal. A menu of five pages on the left, the
// current page on the right. Each page is a module under pages/ with one
// exported render(container, context) that fills the container.

import * as costPage from "./pages/cost.js";
import * as euAiActPage from "./pages/eu-ai-act.js";
import * as evalPage from "./pages/eval.js";
import * as modelsPage from "./pages/models.js";
import * as tracePage from "./pages/trace.js";

const backdrop = document.getElementById("settings");
const menu = document.getElementById("settings-menu");
const pageContainer = document.getElementById("settings-page");
const gear = document.getElementById("gear");
const closeButton = document.getElementById("settings-close");

// Menu key (the data-page attribute in index.html) to the function that renders that page.
const PAGES = {
  models: (container) => modelsPage.render(container),
  trace: (container, context) => tracePage.render(container, context),
  eval: (container) => evalPage.render(container),
  cost: (container) => costPage.render(container),
  "eu-ai-act": (container) => euAiActPage.render(container),
};

// Open the modal on a page. traceId only matters for the Trace page; without it the latest trace shows.
export function openSettings(page = "models", traceId) {
  backdrop.hidden = false;
  showPage(page, { traceId });
  closeButton.focus();
}

export function closeSettings() {
  backdrop.hidden = true;
  // Emptying the page tells a polling page (Eval) that it is gone; see pages/eval.js.
  pageContainer.replaceChildren();
  gear.focus();
}

// Called once by app.js at start: wires the gear, the close button, the backdrop, the menu and Escape.
export function initSettings() {
  gear.addEventListener("click", () => openSettings());
  closeButton.addEventListener("click", closeSettings);
  backdrop.addEventListener("click", onBackdropClick);
  menu.addEventListener("click", onMenuClick);
  document.addEventListener("keydown", onKeyDown);
}

function showPage(page, context) {
  const render = PAGES[page];
  if (!render) {
    return;
  }
  markActive(page);
  pageContainer.replaceChildren();
  render(pageContainer, context);
}

function markActive(page) {
  for (const item of menu.querySelectorAll(".menu-item")) {
    item.classList.toggle("active", item.dataset.page === page);
  }
}

function onMenuClick(event) {
  const item = event.target.closest(".menu-item");
  if (!item) {
    return;
  }
  showPage(item.dataset.page, {});
}

// Clicks inside the dialog bubble up to the backdrop too; only a click on the dimmed area itself closes.
function onBackdropClick(event) {
  if (event.target === backdrop) {
    closeSettings();
  }
}

function onKeyDown(event) {
  if (event.key === "Escape" && !backdrop.hidden) {
    closeSettings();
  }
}
