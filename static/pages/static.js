// static.js: the two placeholder pages, Model suitability and EU AI Act.
// They share this module and differ only by title.

import { el } from "../dom.js";

export function render(container, title) {
  container.append(el("h3", "heading", title), el("p", "muted", "Filled in after the eval results are in."));
}
