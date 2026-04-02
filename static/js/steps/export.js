// ───────── EXPORT ─────────
function renderExport(c, f) {
  stopStream();
  updateCamDot(false);
  $("#stream-img").style.display = "none";
  $("#placeholder").style.display = "flex";
  const cal = calibrationResult || {};
  const ext = extrinsicResult;
  const he = handeyeResult;

  c.innerHTML = `
    <div class="section-label">Export Calibration</div>
    <div class="hint">Download your calibration as a <strong>JSON file</strong> containing all intrinsic, extrinsic, and hand-eye parameters.</div>

    <div class="card">
      <div style="font-size:13px;color:var(--text);margin-bottom:8px;font-weight:500">Summary</div>
      <div style="font-size:12px;line-height:2;font-family:var(--mono)">
        <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Resolution</span><span>${cal.image_size ? cal.image_size[0] + "×" + cal.image_size[1] : "—"}</span></div>
        <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Focal length</span><span>${fmtNum(cal.fx)} × ${fmtNum(cal.fy)} px</span></div>
        <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Principal pt</span><span>(${fmtNum(cal.cx)}, ${fmtNum(cal.cy)})</span></div>
        <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Intrinsic RPE</span><span style="color:${(cal.rpe||1) < 0.5 ? 'var(--green)' : 'var(--amber)'}">${fmtNum(cal.rpe, 4)} px</span></div>
        ${ext ? `
        <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Tag distance</span><span>${fmtNum(Math.sqrt(ext.t[0]**2+ext.t[1]**2+ext.t[2]**2)*100, 1)} cm</span></div>
        <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Extrinsic RPE</span><span style="color:${ext.rpe < 1 ? 'var(--green)' : 'var(--amber)'}">${fmtNum(ext.rpe, 4)} px</span></div>
        ` : '<div style="color:var(--text-micro)">Extrinsic: not calibrated</div>'}
        ${he ? `
        <div style="height:1px;background:var(--border);margin:6px 0"></div>
        <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Hand-Eye</span><span style="color:var(--green)">${he.method} (${he.config})</span></div>
        <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">HE Residual</span><span>${fmtNum(he.residual, 6)}</span></div>
        <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Pose pairs</span><span>${he.num_pairs}</span></div>
        ` : '<div style="color:var(--text-micro)">Hand-Eye: not calibrated</div>'}
      </div>
    </div>

    <a href="/api/export" download="calibration.json" class="btn primary full" style="text-align:center;text-decoration:none;display:block;margin-bottom:14px">⬇ Download calibration.json</a>

    <div class="section-label">JSON Preview</div>
    <div class="card" style="font-family:var(--mono);font-size:10px;line-height:1.6;max-height:300px;overflow-y:auto;white-space:pre-wrap;color:var(--text-dim);word-break:break-all" id="json-preview">Loading…</div>

    <div class="card" style="margin-top:14px;border-color:rgba(74,124,255,0.15)">
      <div style="font-size:12px;color:var(--accent-light);line-height:1.6">
        <strong>Usage in OpenCV (Python):</strong>
        <pre style="margin-top:8px;font-size:10px;color:var(--text-dim);white-space:pre-wrap">import json, numpy as np
data = json.load(open("calibration.json"))
K = np.array(data["intrinsic"]["camera_matrix"])
dist = np.array(data["intrinsic"]["distortion_coefficients"])${he ? `
T_he = np.eye(4)
T_he[:3,:3] = np.array(data["hand_eye"]["rotation_matrix"])
T_he[:3,3] = data["hand_eye"]["translation_vector"]` : ''}</pre>
      </div>
    </div>`;

  // Fetch preview
  fetch("/api/export").then(r => r.json()).then(d => {
    const el = document.getElementById("json-preview");
    if (el) el.textContent = JSON.stringify(d, null, 2);
  });

  f.innerHTML = `
    <button class="btn" onclick="goStep(9)">← Adjust</button>
    <button class="btn" onclick="goStep(0)">Start Over</button>`;
}
