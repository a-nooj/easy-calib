// ───────── CAPTURE (INTRINSIC) ─────────
function renderCapture(c, f) {
  const minCap = 4;
  c.innerHTML = `
    <div class="section-label">Capture ChArUco Views</div>
    <div class="hint">Point your camera at the printed ChArUco board. The overlay shows detected corners in <em>orange</em>. Move the board to different positions and angles.</div>
    <div class="progress-bar"><div class="fill" id="cap-progress" style="width:${Math.min(100, (captures.length / minCap) * 100)}%"></div></div>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
      <span class="badge ${captures.length >= minCap ? 'green' : 'amber'}" id="cap-badge">${captures.length} / ${minCap}+ captures</span>
      <span class="badge blue" id="corner-badge">— corners</span>
    </div>

    <div class="auto-capture-row" id="auto-row">
      <span style="font-size:12px;color:var(--text-dim)">Auto-capture (every 2 s when board visible)</span>
      <button id="auto-btn" class="btn sm ${window._autoCapture ? 'primary' : ''}" onclick="toggleAutoCapture()">
        ${window._autoCapture ? '⏹ Stop Auto' : '⟳ Start Auto'}
      </button>
    </div>

    <div class="card" style="border-color:rgba(52,211,153,0.15)">
      <div style="font-size:12px;color:var(--green);line-height:1.7">
        <strong>Tips for good calibration:</strong><br>
        • Tilt the board at different angles (15–45°)<br>
        • Move it to all four corners of the frame<br>
        • Vary the distance (close and far)<br>
        • Keep the board still when capturing<br>
        • Avoid motion blur — good lighting helps
      </div>
    </div>

    <div class="captures-grid" id="cap-grid"></div>
    <div id="capture-feedback" style="font-size:12px;color:var(--text-dim);text-align:center;min-height:20px"></div>

    <div class="divider"></div>
    <div class="section-label">Import Previous Calibration</div>
    <div class="hint" style="margin-bottom:10px">Already have a <code style="color:var(--accent-light)">calibration.json</code>? Import it to skip straight to the extrinsic step.</div>
    <label class="btn full" style="display:flex;align-items:center;justify-content:center;gap:8px;cursor:pointer">
      ↑ Import calibration.json
      <input type="file" accept=".json" style="display:none" onchange="importIntrinsicJSON(this)">
    </label>`;

  renderCaptureGrid();

  f.innerHTML = `
    <button class="btn danger sm" onclick="clearCaptures()">Clear All</button>
    <button class="btn" style="flex:1" id="snap-btn" onclick="snapIntrinsic()">📸 Capture Frame</button>
    <button class="btn primary" id="cal-btn" ${captures.length < minCap ? 'disabled' : ''} onclick="goStep(3);runCalibration()">Calibrate →</button>`;

  // Live corner count + auto-capture thumbnail sync
  if (!window._capInterval) {
    window._capInterval = setInterval(() => {
      if (currentStep !== 2) { clearInterval(window._capInterval); window._capInterval = null; return; }
      const b = document.getElementById("corner-badge");
      if (b && lastStatus.charuco_count !== undefined) {
        b.textContent = `${lastStatus.charuco_count} corners`;
        b.className = "badge " + (lastStatus.charuco_enough ? "green" : "amber");
      }
      // Sync thumbnails added by auto-capture on the backend
      if (lastStatus.num_captures !== undefined && lastStatus.num_captures > captures.length) {
        _syncAutoCaptureThumbnails();
      }
    }, 300);
  }
}

async function _syncAutoCaptureThumbnails() {
  const r = await api('/api/capture/latest_thumbnail');
  if (!r.ok) return;
  // Push all missing thumbnails (backend may have added multiple since last check)
  while (captures.length < r.num_captures) {
    captures.push(r.thumbnail); // latest thumbnail fills the gap; acceptable for display
  }
  renderCaptureGrid();
  const p = document.getElementById("cap-progress");
  if (p) p.style.width = Math.min(100, (captures.length / 4) * 100) + "%";
  const b = document.getElementById("cap-badge");
  if (b) {
    b.textContent = `${captures.length} / 4+ captures`;
    b.className = "badge " + (captures.length >= 4 ? "green" : "amber");
  }
  const cb = document.getElementById("cal-btn");
  if (cb && captures.length >= 4) cb.disabled = false;
}

function renderCaptureGrid() {
  const grid = document.getElementById("cap-grid");
  if (!grid) return;
  grid.innerHTML = captures.map((t, i) =>
    `<div class="capture-thumb"><img src="data:image/jpeg;base64,${t}" /><div class="idx">#${i + 1}</div></div>`
  ).join("");
}

window.toggleAutoCapture = async function() {
  window._autoCapture = !window._autoCapture;
  const r = await post('/api/capture/auto', { enabled: window._autoCapture, mode: 'intrinsic' });
  if (!r.ok) { window._autoCapture = false; toast(r.error || 'Failed', false); }
  // Re-render to update button state
  renderCapture($("#sidebar-content"), $("#sidebar-footer"));
  if (window._autoCapture) toast('Auto-capture ON — hold the board still');
};

window.snapIntrinsic = async function() {
  const btn = document.getElementById("snap-btn");
  const fb = document.getElementById("capture-feedback");
  btn.disabled = true;
  btn.textContent = "Capturing…";
  const r = await post("/api/capture/intrinsic");
  btn.disabled = false;
  btn.textContent = "📸 Capture Frame";
  if (r.ok) {
    captures.push(r.thumbnail);
    toast(`Captured! ${r.corners_found} corners detected`);
    fb.style.color = "var(--green)";
    fb.textContent = `Frame #${captures.length} saved — ${r.corners_found} corners`;
    renderCaptureGrid();
    const p = document.getElementById("cap-progress");
    if (p) p.style.width = Math.min(100, (captures.length / 4) * 100) + "%";
    const b = document.getElementById("cap-badge");
    if (b) { b.textContent = `${captures.length} / 4+ captures`; b.className = "badge " + (captures.length >= 4 ? "green" : "amber"); }
    const cb = document.getElementById("cal-btn");
    if (cb && captures.length >= 4) cb.disabled = false;
  } else {
    toast(r.error || "Capture failed", false);
    fb.style.color = "var(--red)";
    fb.textContent = r.error || "Not enough corners — reposition the board";
  }
};

window.clearCaptures = function() {
  captures = [];
  window._autoCapture = false;
  post("/api/capture/auto", { enabled: false });
  post("/api/capture/clear");
  renderCapture($("#sidebar-content"), $("#sidebar-footer"));
};

window.importIntrinsicJSON = async function(input) {
  const file = input.files[0];
  if (!file) return;
  let data;
  try { data = JSON.parse(await file.text()); }
  catch { toast('Invalid JSON file', false); return; }

  const r = await post('/api/load', data);
  if (!r.ok) { toast(r.error || 'Import failed', false); return; }
  if (!r.loaded.intrinsic) { toast('No intrinsic calibration found in file', false); return; }

  // Populate calibrationResult from the uploaded JSON
  const intr = data.intrinsic;
  if (!intr) { toast('Missing intrinsic section', false); return; }
  const params = intr.parameters || {};
  const K = intr.camera_matrix;
  const dist = intr.distortion_coefficients;
  const d = Array.isArray(dist[0]) ? dist[0] : dist;
  calibrationResult = {
    fx: params.fx !== undefined ? params.fx : K[0][0],
    fy: params.fy !== undefined ? params.fy : K[1][1],
    cx: params.cx !== undefined ? params.cx : K[0][2],
    cy: params.cy !== undefined ? params.cy : K[1][2],
    k1: params.k1 !== undefined ? params.k1 : (d[0] || 0),
    k2: params.k2 !== undefined ? params.k2 : (d[1] || 0),
    p1: params.p1 !== undefined ? params.p1 : (d[2] || 0),
    p2: params.p2 !== undefined ? params.p2 : (d[3] || 0),
    rpe: intr.reprojection_error || 0,
    per_view_errors: [],
    image_size: intr.image_size || [1280, 720],
    K: K,
    dist: dist,
    num_frames: 0,
  };
  toast('Calibration imported — skipping to result');
  goStep(3);
};

// ───────── INTRINSIC RESULT ─────────
async function runCalibration() {
  // Stop auto-capture if it was running
  if (window._autoCapture) {
    window._autoCapture = false;
    await post('/api/capture/auto', { enabled: false });
  }
  const c = $("#sidebar-content");
  c.innerHTML = `
    <div class="section-label">Calibrating…</div>
    <div class="hint">Running Zhang's method on ${captures.length} captured frames. This may take a moment.</div>
    <div style="text-align:center;padding:40px"><div class="badge blue">⏳ Computing…</div></div>`;
  const r = await post("/api/calibrate/intrinsic");
  if (r.ok) {
    calibrationResult = r.result;
    toast(`Calibration complete — RPE: ${r.result.rpe} px`);
    renderIntrinsic($("#sidebar-content"), $("#sidebar-footer"));
  } else {
    toast(r.error || "Calibration failed", false);
    c.innerHTML = `
      <div class="section-label" style="color:var(--red)">Calibration Failed</div>
      <div class="hint">${r.error || "Unknown error"}. Try capturing more frames from diverse angles.</div>`;
    $("#sidebar-footer").innerHTML = `<button class="btn full" onclick="goStep(2)">← Back to Capture</button>`;
  }
}

function renderIntrinsic(c, f) {
  if (!calibrationResult) { runCalibration(); return; }
  const r = calibrationResult;
  stopStream();
  startStream("undistort");
  c.innerHTML = `
    <div class="section-label">Intrinsic Calibration Result</div>
    <div class="hint">Camera intrinsics estimated${r.num_frames ? ` from <strong>${r.num_frames} frames</strong>` : ''}. The live feed now shows the <em>undistorted</em> image.</div>
    <div style="display:flex;gap:8px;margin-bottom:14px">
      <span class="badge ${r.rpe < 0.5 ? 'green' : r.rpe < 1.0 ? 'amber' : 'red'}">RPE: ${r.rpe} px</span>
      <span class="badge blue">${r.image_size[0]}×${r.image_size[1]}</span>
      ${r.num_frames === 0 ? '<span class="badge amber">Imported</span>' : ''}
    </div>

    <div class="section-label">Camera Matrix K</div>
    <div class="matrix">
      <div style="display:flex;justify-content:space-between"><span class="val">${fmtNum(r.fx)}</span><span>0</span><span class="val">${fmtNum(r.cx)}</span></div>
      <div style="display:flex;justify-content:space-between"><span>0</span><span class="val">${fmtNum(r.fy)}</span><span class="val">${fmtNum(r.cy)}</span></div>
      <div style="display:flex;justify-content:space-between"><span>0</span><span>0</span><span>1</span></div>
    </div>

    <div class="section-label">Distortion Coefficients</div>
    <div class="card" style="font-family:var(--mono);font-size:11px;line-height:2">
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">k₁</span><span class="val">${fmtNum(r.k1, 6)}</span></div>
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">k₂</span><span class="val">${fmtNum(r.k2, 6)}</span></div>
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">p₁</span><span class="val">${fmtNum(r.p1, 6)}</span></div>
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">p₂</span><span class="val">${fmtNum(r.p2, 6)}</span></div>
    </div>

    ${r.per_view_errors.length > 0 ? `
    <div class="section-label">Per-View Reprojection Error</div>
    <div class="card" style="font-family:var(--mono);font-size:11px">
      ${r.per_view_errors.map((e, i) => `<div style="display:flex;justify-content:space-between;line-height:1.8"><span style="color:var(--text-dim)">Frame ${i+1}</span><span style="color:${e < 0.5 ? 'var(--green)' : e < 1 ? 'var(--amber)' : 'var(--red)'}">${e} px</span></div>`).join("")}
    </div>` : ''}

    <div class="card" style="border-color:rgba(52,211,153,0.15)">
      <div style="font-size:12px;color:var(--green);line-height:1.6">
        ${r.num_frames === 0
          ? "↑ Imported calibration loaded. Review the values and proceed."
          : r.rpe < 0.5 ? "✓ Excellent calibration! RPE < 0.5 px is very good."
          : r.rpe < 1.0 ? "⚠ Decent calibration. For better results, capture more frames from diverse angles."
          : "⚠ High reprojection error. Consider recapturing with more frames and better angles."}
      </div>
    </div>`;
  f.innerHTML = `
    <button class="btn" onclick="goStep(2)">← Recapture</button>
    <button class="btn primary" style="flex:1" onclick="goStep(4)">Extrinsic Calibration →</button>`;
}
