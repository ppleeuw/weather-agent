// format.js: pure formatting helpers. No DOM and no network: each one turns a
// number or a string into a string and does nothing else, so it is easy to
// read in isolation and easy to test.

// Money as "$0.0021": four decimals because one request costs tenths of a cent.
export function formatCost(usd) {
  const value = Number(usd) || 0;
  return "$" + value.toFixed(4);
}

// List prices per million tokens as "$1.50".
export function formatPrice(usd) {
  const value = Number(usd) || 0;
  return "$" + value.toFixed(2);
}

// "640 ms" under a second, "1.8 s" from a second up.
export function formatLatency(ms) {
  const value = Math.round(Number(ms) || 0);
  if (value < 1000) {
    return value + " ms";
  }
  return (value / 1000).toFixed(1) + " s";
}

// Token counts as "812 in / 46 out".
export function formatTokens(inputTokens, outputTokens) {
  return (inputTokens || 0) + " in / " + (outputTokens || 0) + " out";
}

// An eval layer {passed, applicable} as "14/15"; a layer with nothing to check shows "n/a".
export function formatRate(layer) {
  if (!layer || !layer.applicable) {
    return "n/a";
  }
  return layer.passed + "/" + layer.applicable;
}

// "2026-09-16T10:31:05+00:00" becomes "2026-09-16 10:31 UTC".
// Every timestamp the server writes is UTC, so the suffix is fixed text.
export function formatTime(iso) {
  if (typeof iso !== "string" || iso.length < 16) {
    return "";
  }
  return iso.slice(0, 16).replace("T", " ") + " UTC";
}
