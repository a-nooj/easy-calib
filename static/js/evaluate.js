// ═══════════════════════════════════════════════════════════════
//  EVALUATE PANEL
// ═══════════════════════════════════════════════════════════════

let _evalLiveActive = false;
let _evalPollInterval = null;

function _evalHeatmapCol(name, label, url, errMsg) {
  const t = Date.now();
  return `
    <div style="flex:1;display:flex;flex-direction:column;min-width:0;gap:6px">
      <div style="font-size:10px;font-family:var(--mono);color:var(--text-micro);text-transform:uppercase;letter-spacing:0.1em;text-align:center">${label}</div>
      <div style="flex:1;position:relative;min-height:0;overflow:hidden;border-radius:8px">
        <img id="ev-img-${name}" src="${url}?t=${t}"
          style="width:100%;height:100%;object-fit:contain;display:block;border:1px solid var(--border);border-radius:8px"
          onerror="evalImgError('${name}')" />
        <div id="ev-ph-${name}"
          style="display:none;position:absolute;inset:0;border:1px solid var(--border);border-radius:8px;background:var(--panel2);flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:16px;text-align:center">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity:0.25"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
          <span style="font-size:11px;color:var(--text-dim)">${errMsg}</span>
        </div>
      </div>
    </div>
  `;
}

window.renderEvaluatePanel = function() {
  stopStream();
  _evalLiveActive = false;
  if (_evalPollInterval) { clearInterval(_evalPollInterval); _evalPollInterval = null; }

  $("#placeholder").style.display = "none";
  $("#stream-img").style.display = "none";

  const evalArea = $("#evaluate-area");
  evalArea.style.display = "flex";
  evalArea.innerHTML = `
    <div style="display:flex;width:100%;height:100%;gap:8px;padding:12px;box-sizing:border-box">
      ${_evalHeatmapCol("coverage",     "Corner Coverage",      "/api/evaluate/coverage",     "No data yet")}
      ${_evalHeatmapCol("reprojection", "Reprojection Error",   "/api/evaluate/reprojection", "Requires calibration")}
      ${_evalHeatmapCol("distortion",   "Distortion Magnitude", "/api/evaluate/distortion",   "Requires calibration")}
    </div>
  `;

  const hasCal = !!calibrationResult;
  const content = $("#sidebar-content");
  const footer  = $("#sidebar-footer");

  content.innerHTML = `
    <div class="section-label" style="margin-top:0">Import Calibration</div>
    <div class="hint">Paste your <code style="color:var(--accent-light)">calibration.json</code> below, or upload a file.</div>
    <div id="eval-cal-status" style="font-size:11px;margin-bottom:6px;min-height:16px">
      ${hasCal
        ? '<span style="color:var(--green)">&#10003; Calibration loaded</span>'
        : '<span style="color:var(--text-dim)">Not loaded</span>'}
    </div>
    <textarea class="debug-import-area" id="eval-json-input" placeholder='{"intrinsic":{...}}'></textarea>
    <div style="display:flex;gap:8px;margin-top:8px">
      <label class="btn sm" style="flex:1;text-align:center;cursor:pointer">
        Upload File
        <input type="file" accept=".json" style="display:none" onchange="evalLoadFile(event)" />
      </label>
      <button class="btn primary sm" style="flex:1" onclick="evalLoadJSON()">Load JSON</button>
    </div>
    <div id="eval-load-status" style="font-size:11px;margin-top:6px;min-height:16px;color:var(--text-dim)"></div>

    <div class="divider"></div>

    <div class="section-label">Live Coverage</div>
    <div class="hint" style="margin-bottom:10px">Start a live feed and move the ChArUco board to accumulate coverage in real time.</div>
    <div style="display:flex;gap:8px">
      <button class="btn primary" style="flex:1" onclick="evalStartLive()">&#9654; Start Live</button>
      <button class="btn" onclick="evalResetAcc()">Clear</button>
    </div>

    <div class="divider"></div>

    <div class="section-label">Corner Coverage</div>
    <div style="height:10px;border-radius:4px;background:linear-gradient(to right,#000004,#3b0f70,#8c2981,#de4968,#fe9f6d,#fcfdbf);margin-bottom:6px"></div>
    <div style="display:flex;justify-content:space-between;font-size:10px;font-family:var(--mono);color:var(--text-dim);margin-bottom:10px"><span>No data</span><span>Dense</span></div>
    <div class="hint" style="margin-bottom:0">Bright zones show where ChArUco corners were detected. <strong>Point the board at dark areas</strong> to improve coverage and calibration quality.</div>

    <div class="divider"></div>

    <div class="section-label">Reprojection Error</div>
    <div style="height:10px;border-radius:4px;background:linear-gradient(to right,#00cc44,#88cc00,#cc4400,#cc0000);margin-bottom:6px"></div>
    <div style="display:flex;justify-content:space-between;font-size:10px;font-family:var(--mono);color:var(--text-dim);margin-bottom:10px"><span>Low (good)</span><span>High (poor)</span></div>
    <div class="hint" style="margin-bottom:0">Red zones show where the calibration model fits poorly. <strong>Recapture with the board in red areas</strong> to reduce spatial error.</div>

    <div class="divider"></div>

    <div class="section-label">Distortion Magnitude</div>
    <div style="height:10px;border-radius:4px;background:linear-gradient(to right,#000004,#1d1147,#721f81,#b63679,#f1605d,#feaf77,#fcfdbf);margin-bottom:6px"></div>
    <div style="display:flex;justify-content:space-between;font-size:10px;font-family:var(--mono);color:var(--text-dim);margin-bottom:10px"><span>Low</span><span>High</span></div>
    <div class="hint" style="margin-bottom:0">Bright regions have the most lens distortion. <strong>AprilTag detections in bright areas benefit most</strong> from an accurate distortion model.</div>
  `;

  footer.innerHTML = `
    <button class="btn primary" style="flex:1" onclick="evalRefresh()">&#8635; Refresh</button>
    <button class="btn" onclick="switchTab('calibrate')">&#8592; Calibrate</button>
  `;
};

function _renderEvalSidebarLive() {
  const content = $("#sidebar-content");
  const footer  = $("#sidebar-footer");
  const t = Date.now();

  content.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
      <span style="display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;color:var(--green)">
        <span style="width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block"></span>
        Live
      </span>
      <button class="btn sm danger" style="flex:1" onclick="evalStopLive()">&#9632; Stop Live</button>
      <button class="btn sm" onclick="evalResetAcc()">Clear</button>
    </div>
    <div class="hint" style="margin-bottom:12px">Move the board to accumulate coverage. Thumbnails update every second.</div>

    <div class="divider"></div>

    <div class="section-label">Corner Coverage</div>
    <img id="ev-th-coverage" src="/api/evaluate/coverage?t=${t}"
      style="width:100%;height:auto;border-radius:6px;border:1px solid var(--border);display:block;margin-bottom:12px"
      onerror="this.style.opacity='0.15'" />

    <div class="section-label">Reprojection Error</div>
    <img id="ev-th-reprojection" src="/api/evaluate/reprojection?t=${t}"
      style="width:100%;height:auto;border-radius:6px;border:1px solid var(--border);display:block;margin-bottom:12px"
      onerror="this.style.opacity='0.15'" />

    <div class="section-label">Distortion Magnitude</div>
    <img id="ev-th-distortion" src="/api/evaluate/distortion?t=${t}"
      style="width:100%;height:auto;border-radius:6px;border:1px solid var(--border);display:block;margin-bottom:12px"
      onerror="this.style.opacity='0.15'" />
  `;

  footer.innerHTML = `
    <button class="btn danger" style="flex:1" onclick="evalStopLive()">&#9632; Stop Live</button>
    <button class="btn" onclick="switchTab('calibrate')">&#8592; Calibrate</button>
  `;
}

window.evalStartLive = function() {
  _evalLiveActive = true;
  $("#evaluate-area").style.display = "none";
  startStream("evaluate");
  updateCamDot(true);
  _renderEvalSidebarLive();
  _evalPollInterval = setInterval(_evalRefreshThumbnails, 1000);
};

window.evalStopLive = function() {
  _evalLiveActive = false;
  if (_evalPollInterval) { clearInterval(_evalPollInterval); _evalPollInterval = null; }
  stopStream();
  updateCamDot(false);
  renderEvaluatePanel();
};

window.evalCleanup = function() {
  _evalLiveActive = false;
  if (_evalPollInterval) { clearInterval(_evalPollInterval); _evalPollInterval = null; }
};

window.evalResetAcc = function() {
  post("/api/evaluate/reset").then(() => {
    if (_evalLiveActive) {
      _evalRefreshThumbnails();
    } else {
      evalRefresh();
    }
  });
};

function _evalRefreshThumbnails() {
  const t = Date.now();
  ["coverage", "reprojection", "distortion"].forEach(name => {
    const img = document.getElementById("ev-th-" + name);
    if (img) {
      img.style.opacity = "1";
      img.src = "/api/evaluate/" + name + "?t=" + t;
    }
  });
}

window.evalImgError = function(name) {
  const img = document.getElementById("ev-img-" + name);
  const ph  = document.getElementById("ev-ph-"  + name);
  if (img) img.style.display = "none";
  if (ph)  ph.style.display  = "flex";
};

window.evalRefresh = function() {
  const t = Date.now();
  ["coverage", "reprojection", "distortion"].forEach(name => {
    const img = document.getElementById("ev-img-" + name);
    const ph  = document.getElementById("ev-ph-"  + name);
    if (!img) return;
    if (ph)  ph.style.display  = "none";
    img.style.display = "block";
    img.src = "/api/evaluate/" + name + "?t=" + t;
  });
};

window.evalLoadJSON = async function() {
  const ta = document.getElementById("eval-json-input");
  const status = document.getElementById("eval-load-status");
  if (!ta || !ta.value.trim()) {
    if (status) status.innerHTML = '<span style="color:var(--red)">Paste JSON first</span>';
    return;
  }
  let data;
  try {
    data = JSON.parse(ta.value.trim());
  } catch (e) {
    if (status) status.innerHTML = `<span style="color:var(--red)">Invalid JSON: ${e.message}</span>`;
    return;
  }
  await _evalApplyJSON(data, status);
};

window.evalLoadFile = function(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async (e) => {
    const status = document.getElementById("eval-load-status");
    let data;
    try {
      data = JSON.parse(e.target.result);
    } catch (err) {
      if (status) status.innerHTML = '<span style="color:var(--red)">Invalid JSON file</span>';
      return;
    }
    const ta = document.getElementById("eval-json-input");
    if (ta) ta.value = JSON.stringify(data, null, 2);
    await _evalApplyJSON(data, status);
  };
  reader.readAsText(file);
};

async function _evalApplyJSON(data, statusEl) {
  const r = await post("/api/load", data);
  if (!r.ok) {
    if (statusEl) statusEl.innerHTML = `<span style="color:var(--red)">&#10007; ${r.error || 'Load failed'}</span>`;
    return;
  }

  const parts = [];
  if (r.loaded.intrinsic) parts.push("Intrinsics");
  if (r.loaded.extrinsic) parts.push("Extrinsic");
  if (r.loaded.hand_eye)  parts.push("Hand-Eye");

  if (statusEl) statusEl.innerHTML = `<span style="color:var(--green)">&#10003; Loaded: ${parts.join(", ")}</span>`;
  toast(`Loaded: ${parts.join(", ")}`);

  // Sync local state from canonical export
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

  if (r.loaded.extrinsic && exportData.extrinsic) {
    const ex = exportData.extrinsic;
    extrinsicResult = {
      R: ex.rotation_matrix,
      t: ex.translation_vector,
      rvec: ex.rodrigues_vector,
      tag_id: ex.tag_id,
      tag_size: ex.tag_size_meters,
      rpe: ex.reprojection_error,
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

  // Update cal status badge without full re-render
  const calStatus = document.getElementById("eval-cal-status");
  if (calStatus) calStatus.innerHTML = '<span style="color:var(--green)">&#10003; Calibration loaded</span>';

  evalRefresh();
}
