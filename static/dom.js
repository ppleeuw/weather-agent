// dom.js: the few DOM helpers every page shares.
//
// Model answers and API text are untrusted, so everything goes through
// textContent. No module in this front end uses innerHTML.

// A new element with an optional class and text: el("p", "muted", "Hello").
export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined && text !== null) {
    node.textContent = String(text);
  }
  return node;
}

// A pass or fail pill. The classes ok and fail come from styles.css.
export function badge(ok, okText = "ok", failText = "fail") {
  if (ok) {
    return el("span", "badge ok", okText);
  }
  return el("span", "badge fail", failText);
}

// The error message component: one sentence; the "!" icon comes from the stylesheet.
export function errorBox(message) {
  const box = el("div", "error", message);
  box.setAttribute("role", "alert");
  return box;
}

// A table from a list of header texts and rows of cells. A cell is text or an element.
export function table(headers, rows) {
  const node = el("table", "table");
  const head = el("thead");
  const headRow = el("tr");
  for (const header of headers) {
    headRow.append(el("th", "", header));
  }
  head.append(headRow);
  const body = el("tbody");
  for (const cells of rows) {
    const row = el("tr");
    for (const cell of cells) {
      row.append(cellOf(cell));
    }
    body.append(row);
  }
  node.append(head, body);
  return node;
}

function cellOf(value) {
  const cell = el("td");
  if (value instanceof Node) {
    cell.append(value);
  } else {
    cell.textContent = String(value);
  }
  return cell;
}

// A link that opens in a new tab. Only an https URL becomes a link; anything else stays text,
// because the URL comes from the API and a "javascript:" URL must never become clickable.
export function externalLink(url, text) {
  if (typeof url !== "string" || !url.startsWith("https://")) {
    return el("span", "", text || String(url));
  }
  const link = el("a", "", text || url);
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener";
  return link;
}
