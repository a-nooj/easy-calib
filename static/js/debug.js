// ═══════════════════════════════════════════════════════════════
//  DEBUG & TUNE PANEL
// ═══════════════════════════════════════════════════════════════
let debugTagSize = 50; // mm
let debugLiveMetrics = null;

function renderDebugPanel() {
  const content = $("#sidebar-content");
  const footer = $("#sidebar-footer");

  // Check if we have loaded calibration data
  const hasCal = !!calibrationResult;
  const hasHE = !!handeyeResult;

  content.innerHTML = `
    <div class="section-label" style="font-size:14px;margin-bottom:4px">Debug &amp; Tune</div>
    <div class="hint" style="margin-bottom:18px">Load a previous calibration and fine-tune parameters with a live camera feed. The overlay shows the undistorted image, AprilTag detection, and projected coordinate frames.</div>

    <!-- IMPORT SECTION -->
    <div class="debug-section">
      <div class="section-label">Import Calibration</div>
      <div class="hint">Paste your <code style="color:var(--accent-light)">calibration.json</code> contents below, or upload a file.</div>
      <textarea class="debug-import-area" id="debug-json-input" placeholder='{"intrinsic":{...}, "hand_eye":{...}}'>${hasCal ? '(parameters already loaded)' : ''}</textarea>
      <div style="display:flex;gap:8px;margin-top:8px">
        <label class="btn sm" style="flex:1;text-align:center;cursor:pointer">
          📂 Upload File
          <input type="file" accept=".json" style="display:none" onchange="debugLoadFile(event)" />
        </label>
        <button class="btn primary sm" style="flex:1" onclick="debugLoadJSON()">Load JSON</button>
      </div>
      <div id="debug-load-status" style="font-size:11px;margin-top:6px;min-height:16px;color:var(--text-dim)">
        ${hasCal ? '<span style="color:var(--green)">✓ Intrinsics loaded</span>' : ''}
        ${hasHE ? ' <span style="color:var(--green)">✓ Hand-eye loaded</span>' : ''}
      </div>
    </div>

    <div class="divider"></div>

    <!-- TAG SIZE -->
    <div class="debug-section">
      <div class="section-label">AprilTag Size</div>
      <div style="display:flex;gap:8px;align-items:center">
        <input id="debug-tag-size" type="number" value="${debugTagSize}" min="5" max="500" step="0.1"
          style="flex:1;padding:7px 10px;border-radius:6px;border:1px solid var(--border2);background:var(--panel2);color:var(--text);font-family:var(--mono);font-size:12px"
          onchange="debugTagSize=parseFloat(this.value);post('/api/handeye/config',{tag_size:debugTagSize/1000})" />
        <span style="font-size:11px;color:var(--text-dim);font-family:var(--mono)">mm</span>
      </div>
    </div>

    <div class="divider"></div>

    <!-- LIVE METRICS -->
    <div class="debug-section">
      <div class="section-label">Live Metrics</div>
      <div class="card" id="debug-metrics" style="font-size:11px;min-height:60px">
        <div class="debug-metric"><span class="label">Tag detected</span><span class="value" id="dm-tag">—</span></div>
        <div class="debug-metric"><span class="label">Tag RPE</span><span class="value" id="dm-rpe">—</span></div>
        <div class="debug-metric"><span class="label">Tag distance</span><span class="value" id="dm-dist">—</span></div>
        <div class="debug-metric"><span class="label">HE loaded</span><span class="value" id="dm-he">${hasHE ? '✓' : '—'}</span></div>
      </div>
    </div>

    <div class="divider"></div>

    <!-- INTRINSIC SLIDERS -->
    <div class="debug-section" id="debug-intrinsics-section" style="${hasCal ? '' : 'opacity:0.4;pointer-events:none'}">
      <div class="section-label">Intrinsics</div>
      ${debugMakeSliders("intrinsic")}
    </div>

    <div class="divider"></div>

    <!-- ROBOT-TO-CAMERA TRANSFORM SLIDERS -->
    <div class="debug-section" id="debug-he-section" style="${hasHE ? '' : 'opacity:0.4;pointer-events:none'}">
      <div class="section-label">Robot → Camera Transform</div>
      ${debugMakeSliders("handeye")}
    </div>

    <div class="divider"></div>

    <!-- START STREAM BUTTON -->
    <div class="debug-section">
      <button class="btn primary full" id="debug-stream-btn" onclick="debugToggleStream()" ${hasCal ? '' : 'disabled'}>
        ▶ Start Live Feed
      </button>
    </div>
  `;

  footer.innerHTML = `
    <a href="/api/export" download="calibration.json" class="btn primary" style="flex:1;text-align:center;text-decoration:none">⬇ Export</a>
    <button class="btn" onclick="switchTab('calibrate')">← Wizard</button>
  `;

  // Start live metric updater
  startDebugMetricsPoll();
}

function debugMakeSliders(group) {
  function sl(id, label, value, min, max, step, unit = "") {
    const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
    const dec = step < 0.001 ? 6 : step < 0.1 ? 4 : step < 1 ? 2 : 1;
    return `<div class="slider-group" id="sg-dbg-${id}">
      <div class="slider-header">
        <span class="lbl">${label}</span>
        <input class="val" id="sv-dbg-${id}" type="text" value="${fmtNum(value, dec)}${unit}"
          onchange="sliderValFromInput('dbg-${id}', this, ${min}, ${max}, ${step}, v => onDebugSlider('${group}','${id}',v,${min},${max},${step}))"
          onkeydown="if(event.key==='Enter'){this.blur()}" />
      </div>
      <div class="slider-track">
        <div class="bg"></div>
        <div class="fill" id="sf-dbg-${id}" style="width:${pct}%"></div>
        <input type="range" min="${min}" max="${max}" step="${step}" value="${value}"
          oninput="onDebugSlider('${group}','${id}',this.value,${min},${max},${step})" />
        <div class="thumb" id="st-dbg-${id}" style="left:calc(${pct}% - 6px)"></div>
      </div>
    </div>`;
  }

  if (group === "intrinsic") {
    const cal = calibrationResult || {};
    return [
      sl("fx", "fx", cal.fx || 800, 100, 3000, 1, " px"),
      sl("fy", "fy", cal.fy || 800, 100, 3000, 1, " px"),
      sl("cx", "cx", cal.cx || 640, 0, 1920, 1, " px"),
      sl("cy", "cy", cal.cy || 360, 0, 1080, 1, " px"),
      '<div style="height:8px"></div>',
      sl("k1", "k1", cal.k1 || 0, -2, 2, 0.0001),
      sl("k2", "k2", cal.k2 || 0, -1, 1, 0.0001),
      sl("p1", "p1", cal.p1 || 0, -0.1, 0.1, 0.00001),
      sl("p2", "p2", cal.p2 || 0, -0.1, 0.1, 0.00001),
    ].join("");
  }

  // handeye
  const he = handeyeResult || {};
  const rv = he.rvec || [0, 0, 0];
  const t = he.t || [0, 0, 0];
  return [
    '<div style="font-size:10px;color:var(--text-micro);margin-bottom:6px">Rotation (Rodrigues)</div>',
    sl("hrv0", "rvec[0]", rv[0], -3.15, 3.15, 0.001, " rad"),
    sl("hrv1", "rvec[1]", rv[1], -3.15, 3.15, 0.001, " rad"),
    sl("hrv2", "rvec[2]", rv[2], -3.15, 3.15, 0.001, " rad"),
    '<div style="height:8px"></div>',
    '<div style="font-size:10px;color:var(--text-micro);margin-bottom:6px">Translation</div>',
    sl("htx", "tx", t[0], -2, 2, 0.0005, " m"),
    sl("hty", "ty", t[1], -2, 2, 0.0005, " m"),
    sl("htz", "tz", t[2], -2, 2, 0.0005, " m"),
  ].join("");
}

let _debugSliderTimeout = null;
window.onDebugSlider = function(group, id, rawVal, min, max, step) {
  const val = parseFloat(rawVal);
  const pct = ((val - min) / (max - min)) * 100;
  const sv = document.getElementById("sv-dbg-" + id);
  const sf = document.getElementById("sf-dbg-" + id);
  const st = document.getElementById("st-dbg-" + id);
  const dec = step < 0.001 ? 6 : step < 0.1 ? 4 : step < 1 ? 2 : 1;
  const unit = id.startsWith("h") && id.includes("rv") ? " rad"
             : id.startsWith("ht") ? " m"
             : id === "fx" || id === "fy" || id === "cx" || id === "cy" ? " px" : "";
  if (sv) sv.value = fmtNum(val, dec) + unit;
  if (sf) sf.style.width = pct + "%";
  if (st) st.style.left = `calc(${pct}% - 6px)`;

  clearTimeout(_debugSliderTimeout);
  _debugSliderTimeout = setTimeout(() => {
    if (group === "intrinsic") {
      const params = {};
      ["fx","fy","cx","cy","k1","k2","p1","p2"].forEach(k => {
        const el = document.querySelector(`#sg-dbg-${k} input[type=range]`);
        if (el) params[k] = parseFloat(el.value);
      });
      post("/api/adjust/intrinsic", params).then(r => {
        if (r.ok && r.result) calibrationResult = r.result;
      });
    } else {
      const rvec = [0,1,2].map(i => {
        const el = document.querySelector(`#sg-dbg-hrv${i} input[type=range]`);
        return el ? parseFloat(el.value) : 0;
      });
      const t = ["htx","hty","htz"].map(k => {
        const el = document.querySelector(`#sg-dbg-${k} input[type=range]`);
        return el ? parseFloat(el.value) : 0;
      });
      post("/api/adjust/handeye", { rvec, t }).then(r => {
        if (r.ok && r.result) handeyeResult = r.result;
      });
    }
  }, 80);
}

let _debugStreamActive = false;
window.debugToggleStream = function() {
  const btn = document.getElementById("debug-stream-btn");
  if (_debugStreamActive) {
    stopStream();
    _debugStreamActive = false;
    if (btn) { btn.textContent = "▶ Start Live Feed"; btn.classList.remove("danger"); btn.classList.add("primary"); }
    updateCamDot(false);
  } else {
    startStream("debug");
    _debugStreamActive = true;
    if (btn) { btn.textContent = "■ Stop Feed"; btn.classList.remove("primary"); btn.classList.add("danger"); }
    updateCamDot(true);
  }
}

window.debugLoadJSON = async function() {
  const ta = document.getElementById("debug-json-input");
  const status = document.getElementById("debug-load-status");
  if (!ta || !ta.value.trim()) {
    if (status) { status.innerHTML = '<span style="color:var(--red)">Paste JSON first</span>'; }
    return;
  }
  let data;
  try {
    data = JSON.parse(ta.value.trim());
  } catch (e) {
    if (status) { status.innerHTML = `<span style="color:var(--red)">Invalid JSON: ${e.message}</span>`; }
    return;
  }
  await debugApplyJSON(data, status);
}

window.debugLoadFile = function(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async (e) => {
    const status = document.getElementById("debug-load-status");
    let data;
    try {
      data = JSON.parse(e.target.result);
    } catch (err) {
      if (status) status.innerHTML = `<span style="color:var(--red)">Invalid JSON file</span>`;
      return;
    }
    // Also populate the textarea for visibility
    const ta = document.getElementById("debug-json-input");
    if (ta) ta.value = JSON.stringify(data, null, 2);
    await debugApplyJSON(data, status);
  };
  reader.readAsText(file);
}

async function debugApplyJSON(data, statusEl) {
  const r = await post("/api/load", data);
  if (!r.ok) {
    if (statusEl) statusEl.innerHTML = `<span style="color:var(--red)">❌ ${r.error || 'Load failed'}</span>`;
    return;
  }

  const parts = [];
  if (r.loaded.intrinsic) parts.push("Intrinsics");
  if (r.loaded.extrinsic) parts.push("Extrinsic");
  if (r.loaded.hand_eye) parts.push("Hand-Eye");

  if (statusEl) statusEl.innerHTML = `<span style="color:var(--green)">✓ Loaded: ${parts.join(", ")}</span>`;
  toast(`Loaded: ${parts.join(", ")}`);

  // Sync local state — fetch from export to get the canonical form
  const exportData = await api("/api/export");

  if (r.loaded.intrinsic && exportData.intrinsic) {
    const p = exportData.intrinsic.parameters;
    calibrationResult = {
      ...p,
      rpe: exportData.intrinsic.reprojection_error || 0,
      image_size: exportData.intrinsic.image_size,
      K: exportData.intrinsic.camera_matrix,
      dist: exportData.intrinsic.distortion_coefficients,
      per_view_errors: [],
      num_frames: 0,
    };
  }

  if (r.loaded.hand_eye && exportData.hand_eye) {
    const h = exportData.hand_eye;
    handeyeResult = {
      R: h.rotation_matrix,
      t: h.translation_vector,
      rvec: h.rodrigues_vector,
      method: h.method || "imported",
      config: h.configuration || "imported",
      residual: h.residual || 0,
      num_pairs: h.num_pose_pairs || 0,
      all_methods: h.all_methods || {},
    };
  }

  if (r.loaded.extrinsic && exportData.extrinsic) {
    const e = exportData.extrinsic;
    extrinsicResult = {
      R: e.rotation_matrix,
      t: e.translation_vector,
      rvec: e.rodrigues_vector,
      tag_id: e.tag_id,
      tag_size: e.tag_size_meters,
      rpe: e.reprojection_error,
    };
  }

  // Re-render the panel to enable sections
  renderDebugPanel();
}

let _debugMetricsPoll = null;
function startDebugMetricsPoll() {
  stopDebugMetricsPoll();
  _debugMetricsPoll = setInterval(async () => {
    if (activeTab !== "debug" || !_debugStreamActive) return;
    const s = await api("/api/status");
    const tagEl = document.getElementById("dm-tag");
    const heEl = document.getElementById("dm-he");
    if (tagEl) {
      tagEl.textContent = s.apriltag_detected ? "✓ Yes" : "No";
      tagEl.style.color = s.apriltag_detected ? "var(--green)" : "var(--red)";
    }
    if (heEl) {
      heEl.textContent = s.has_handeye ? "✓ Active" : "—";
      heEl.style.color = s.has_handeye ? "var(--green)" : "var(--text-dim)";
    }
  }, 400);
}

function stopDebugMetricsPoll() {
  if (_debugMetricsPoll) { clearInterval(_debugMetricsPoll); _debugMetricsPoll = null; }
}
