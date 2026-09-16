// models.js: the Models page. Which handler runs each of the four pipeline
// steps, and the offline switch. Every change saves at once with PUT /api/settings.

import { getSettings, putSettings } from "../api.js";
import { el, errorBox } from "../dom.js";

const STEPS = [
  { key: "understand", label: "1 Understand" },
  { key: "geocode", label: "2 Geocode" },
  { key: "forecast", label: "3 Forecast" },
  { key: "answer", label: "4 Answer" },
];

const INTRO =
  "The two model steps can run on four models. The geocode step can use Open-Meteo Geocoding or Nominatim; " +
  "the forecast step runs on Open-Meteo. A change applies to the next question and resets when the server restarts.";

export async function render(container) {
  const heading = el("h3", "heading", "Models");
  container.append(heading, el("p", "muted", INTRO));
  const status = el("p", "small muted"); // "Saved." or the reason it was not
  try {
    const settings = await getSettings();
    if (!heading.isConnected) {
      return; // the user moved to another page while the settings were loading
    }
    for (const step of STEPS) {
      container.append(stepRow(step, settings, status));
    }
    container.append(offlineRow(settings, status), status);
  } catch (error) {
    if (heading.isConnected) {
      container.append(errorBox("Could not load the settings: " + error.message));
    }
  }
}

// A label above a dropdown. The label is inline and the dropdown is full width, so it wraps under the label.
function stepRow(step, settings, status) {
  const row = el("div", "stack");
  const label = el("label", "small muted", step.label);
  label.htmlFor = "setting-" + step.key;
  row.append(label, dropdown(step, settings, status));
  return row;
}

function dropdown(step, settings, status) {
  const select = el("select", "select");
  select.id = "setting-" + step.key;
  for (const optionId of settings.options[step.key] || []) {
    const option = el("option", "", optionId);
    option.value = optionId;
    option.selected = optionId === settings[step.key];
    select.append(option);
  }
  select.addEventListener("change", () => {
    const changes = {};
    changes[step.key] = select.value;
    save(changes, status);
  });
  return select;
}

// A checkbox drawn as a switch by styles.css. Offline forces replay from the recordings.
function offlineRow(settings, status) {
  const label = el("label");
  const box = el("input", "switch");
  box.type = "checkbox";
  box.checked = Boolean(settings.offline);
  box.addEventListener("change", () => save({ offline: box.checked }, status));
  label.append(box, " Offline: replay recordings");
  return label;
}

async function save(changes, status) {
  status.textContent = "Saving…";
  try {
    await putSettings(changes);
    status.textContent = "Saved.";
  } catch (error) {
    status.textContent = "Not saved: " + error.message;
  }
}
