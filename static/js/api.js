// ═══════════════════════════════════════════════════════════════
//  HELPERS
// ═══════════════════════════════════════════════════════════════
const $ = s => document.querySelector(s);

const api = async (path, opts) => {
  try {
    const r = await fetch(path, opts);
    return await r.json();
  } catch (e) { return { ok: false, error: e.message }; }
};

const post = (path, body) => api(path, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: body ? JSON.stringify(body) : undefined,
});

function toast(msg, ok = true) {
  const t = $("#toast");
  t.className = "toast " + (ok ? "ok" : "err");
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(t._t);
  t._t = setTimeout(() => t.style.display = "none", 3000);
}

function fmtNum(v, d = 2) {
  if (typeof v !== "number") return "—";
  return d === 0 ? Math.round(v).toString() : v.toFixed(d);
}

// Shared: sync a typed value from the number input back to the range slider + visuals
function sliderValFromInput(groupId, inputEl, min, max, step, callback) {
  // Strip common unit suffixes before parsing
  let raw = inputEl.value.replace(/\s*(px|rad|m|mm|°)\s*$/i, "").trim();
  let val = parseFloat(raw);
  if (isNaN(val)) return;
  val = Math.max(min, Math.min(max, val));
  const rangeEl = document.querySelector(`#sg-${groupId} input[type=range]`);
  if (rangeEl) { rangeEl.value = val; }
  callback(val);
}
