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
    <div id="capture-feedback" style="font-size:12px;color:var(--text-dim);text-align:center;min-height:20px"></div>`;
  renderCaptureGrid();
  f.innerHTML = `
    <button class="btn danger sm" onclick="clearCaptures()">Clear All</button>
    <button class="btn" style="flex:1" id="snap-btn" onclick="snapIntrinsic()">📸 Capture Frame</button>
    <button class="btn primary" id="cal-btn" ${captures.length < minCap ? 'disabled' : ''} onclick="goStep(3);runCalibration()">Calibrate →</button>`;
  // Live corner count updater
  if (!window._capInterval) {
    window._capInterval = setInterval(() => {
      if (currentStep !== 2) { clearInterval(window._capInterval); window._capInterval = null; return; }
      const b = document.getElementById("corner-badge");
      if (b && lastStatus.charuco_count !== undefined) {
        b.textContent = `${lastStatus.charuco_count} corners`;
        b.className = "badge " + (lastStatus.charuco_enough ? "green" : "amber");
      }
    }, 300);
  }
}

function renderCaptureGrid() {
  const grid = document.getElementById("cap-grid");
  if (!grid) return;
  grid.innerHTML = captures.map((t, i) =>
    `<div class="capture-thumb"><img src="data:image/jpeg;base64,${t}" /><div class="idx">#${i + 1}</div></div>`
  ).join("");
}

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
}

window.clearCaptures = function() {
  captures = [];
  post("/api/capture/clear");
  renderCapture($("#sidebar-content"), $("#sidebar-footer"));
}

// ───────── INTRINSIC RESULT ─────────
async function runCalibration() {
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
    <div class="hint">Camera intrinsics estimated from <strong>${r.num_frames} frames</strong>. The live feed now shows the <em>undistorted</em> image.</div>
    <div style="display:flex;gap:8px;margin-bottom:14px">
      <span class="badge ${r.rpe < 0.5 ? 'green' : r.rpe < 1.0 ? 'amber' : 'red'}">RPE: ${r.rpe} px</span>
      <span class="badge blue">${r.image_size[0]}×${r.image_size[1]}</span>
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

    <div class="section-label">Per-View Reprojection Error</div>
    <div class="card" style="font-family:var(--mono);font-size:11px">
      ${r.per_view_errors.map((e, i) => `<div style="display:flex;justify-content:space-between;line-height:1.8"><span style="color:var(--text-dim)">Frame ${i+1}</span><span style="color:${e < 0.5 ? 'var(--green)' : e < 1 ? 'var(--amber)' : 'var(--red)'}">${e} px</span></div>`).join("")}
    </div>

    <div class="card" style="border-color:rgba(52,211,153,0.15)">
      <div style="font-size:12px;color:var(--green);line-height:1.6">
        ${r.rpe < 0.5 ? "✓ Excellent calibration! RPE < 0.5 px is very good."
          : r.rpe < 1.0 ? "⚠ Decent calibration. For better results, capture more frames from diverse angles."
          : "⚠ High reprojection error. Consider recapturing with more frames and better angles."}
      </div>
    </div>`;
  f.innerHTML = `
    <button class="btn" onclick="goStep(2)">← Recapture</button>
    <button class="btn primary" style="flex:1" onclick="goStep(4)">Extrinsic Calibration →</button>`;
}
