// ═══════════════════════════════════════════════════════════════
//  EVALUATE PANEL
// ═══════════════════════════════════════════════════════════════

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
  $("#placeholder").style.display = "none";
  $("#stream-img").style.display = "none";

  const evalArea = $("#evaluate-area");
  evalArea.style.display = "flex";
  evalArea.innerHTML = `
    <div style="display:flex;width:100%;height:100%;gap:8px;padding:12px;box-sizing:border-box">
      ${_evalHeatmapCol("coverage",     "Corner Coverage",      "/api/evaluate/coverage",     "No captures yet")}
      ${_evalHeatmapCol("reprojection", "Reprojection Error",   "/api/evaluate/reprojection", "Requires captures + calibration")}
      ${_evalHeatmapCol("distortion",   "Distortion Magnitude", "/api/evaluate/distortion",   "Requires calibration")}
    </div>
  `;

  const content = $("#sidebar-content");
  const footer  = $("#sidebar-footer");

  content.innerHTML = `
    <div class="section-label" style="margin-top:0">Calibration Quality</div>
    <div class="hint">Spatial analysis of your calibration. Use these maps to identify gaps in coverage and areas of poor fit.</div>

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
    <button class="btn primary" style="flex:1" onclick="evalRefresh()">↺ Refresh</button>
    <button class="btn" onclick="switchTab('calibrate')">← Calibrate</button>
  `;
};

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
