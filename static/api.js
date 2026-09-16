// api.js: one function per HTTP endpoint of the Weather Agent server.
//
// Every function returns the parsed JSON body. On a non-2xx status it throws
// an Error carrying the server's message, so a caller needs one try/catch and
// never looks at status codes. The one exception is the Trace page, which
// reads error.status to tell "no request yet" (404) from a real failure.

export function ask(question) {
  return request("POST", "/api/ask", { question });
}

export function getSettings() {
  return request("GET", "/api/settings");
}

export function putSettings(changes) {
  return request("PUT", "/api/settings", changes);
}

export function getTrace(id) {
  // Without an id the server returns the latest trace.
  if (!id) {
    return request("GET", "/api/trace");
  }
  return request("GET", "/api/trace/" + encodeURIComponent(id));
}

export function getHealth() {
  return request("GET", "/api/health");
}

export function getCost() {
  return request("GET", "/api/cost");
}

export function getEval() {
  return request("GET", "/api/eval");
}

export function runEval(model) {
  return request("POST", "/api/eval/run", { model });
}

// The only place that calls fetch. body is optional; when given it is sent as JSON.
async function request(method, path, body) {
  const options = { method, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const data = await readJson(response);
  if (!response.ok) {
    throw serverError(data, response);
  }
  return data;
}

// A body that is not JSON (an empty 502, a proxy's HTML page) must not hide the status.
async function readJson(response) {
  try {
    return await response.json();
  } catch (_error) {
    return {};
  }
}

// Our routes answer {"error": "..."}; FastAPI's own errors answer {"detail": ...}.
function serverError(data, response) {
  const message = data.error || data.detail || response.statusText || "HTTP " + response.status;
  const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
  error.status = response.status;
  return error;
}
