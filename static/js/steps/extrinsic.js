// ───────── EXTRINSIC CAPTURE ─────────
function renderExtCapture(c, f) {
  startStream("apriltag");
  updateCamDot(true);
  c.innerHTML = `
    <div class="section-label">AprilTag Extrinsic Calibration</div>
    <div class="hint">Place the printed <strong>AprilTag</strong> at a known location in your scene. Point the camera at it until it's detected (shown in <em>green</em>).</div>

    <div style="margin-bottom:14px">
      <span class="badge amber" id="tag-badge">Searching for tag…</span>
    </div>

    <div class="card">
      <div style="font-size:12px;color:var(--text-dim);line-height:1.7">
        <strong>How it works:</strong><br>
        • The tag's 4 corners define a known 3D square<br>
        • OpenCV's <code style="color:var(--accent-light)">solvePnP</code> finds the camera pose<br>
        • You get the rotation matrix R and translation vector t<br>
        • These describe <em>where the camera is</em> relative to the tag
      </div>
    </div>

    <div class="section-label">Tag Configuration</div>
    <div style="margin-bottom:10px">
      <label style="font-size:10px;font-family:var(--mono);color:var(--text-dim);display:block;margin-bottom:4px">Printed tag size (mm)</label>
      <input id="ext-tag-size" type="number" value="${document.getElementById('tag-size')?.value || 50}" min="5" max="500" step="0.1"
        style="width:100%;padding:8px 10px;border-radius:6px;border:1px solid var(--border2);background:var(--panel2);color:var(--text);font-family:var(--mono);font-size:13px" />
    </div>

    <div class="card" style="border-color:rgba(251,191,36,0.15)">
      <div style="font-size:12px;color:var(--amber);line-height:1.6">
        <strong>Tip:</strong> Keep the tag flat and fully visible. Avoid extreme angles. The closer the tag, the more accurate the pose estimate.
      </div>
    </div>`;
  f.innerHTML = `
    <button class="btn" onclick="goStep(3)">← Back</button>
    <button class="btn primary" style="flex:1" id="ext-snap-btn" onclick="snapExtrinsic()">📸 Capture Tag Pose</button>`;
  // Live tag detection updater
  if (!window._tagInterval) {
    window._tagInterval = setInterval(() => {
      if (currentStep !== 4) { clearInterval(window._tagInterval); window._tagInterval = null; return; }
      const b = document.getElementById("tag-badge");
      if (b && lastStatus.apriltag_detected !== undefined) {
        if (lastStatus.apriltag_detected) {
          b.textContent = "✓ Tag detected — ready to capture";
          b.className = "badge green";
        } else {
          b.textContent = "Searching for tag…";
          b.className = "badge amber";
        }
      }
    }, 300);
  }
}

window.snapExtrinsic = async function() {
  const tagSizeMM = parseFloat(document.getElementById("ext-tag-size")?.value || 50);
  const btn = document.getElementById("ext-snap-btn");
  btn.disabled = true;
  btn.textContent = "Capturing…";
  const r = await post("/api/capture/extrinsic", { tag_size: tagSizeMM / 1000.0 });
  btn.disabled = false;
  btn.textContent = "📸 Capture Tag Pose";
  if (r.ok) {
    extrinsicResult = r.result;
    toast(`Tag #${r.result.tag_id} pose solved — RPE: ${r.result.rpe} px`);
    goStep(5);
  } else {
    toast(r.error || "Capture failed", false);
  }
}

// ───────── EXTRINSIC RESULT ─────────
function renderExtrinsic(c, f) {
  if (!extrinsicResult) { goStep(4); return; }
  const r = extrinsicResult;
  stopStream();

  // Show annotated thumbnail
  const img = document.getElementById("stream-img");
  if (r.thumbnail) {
    img.src = "data:image/jpeg;base64," + r.thumbnail;
    img.style.display = "block";
    document.getElementById("placeholder").style.display = "none";
  }
  updateCamDot(false);

  c.innerHTML = `
    <div class="section-label">Extrinsic Calibration Result</div>
    <div class="hint">Camera pose solved relative to <strong>AprilTag #${r.tag_id}</strong> (size: ${(r.tag_size*1000).toFixed(1)} mm).</div>
    <div style="margin-bottom:14px">
      <span class="badge ${r.rpe < 1 ? 'green' : r.rpe < 3 ? 'amber' : 'red'}">RPE: ${r.rpe} px</span>
    </div>

    <div class="section-label">Rotation Matrix R</div>
    <div class="matrix">
      ${r.R.map(row => `<div style="display:flex;justify-content:space-between">${row.map(v => `<span class="val" style="width:33%">${fmtNum(v, 4)}</span>`).join("")}</div>`).join("")}
    </div>

    <div class="section-label">Translation Vector t</div>
    <div class="matrix">
      <div style="display:flex;gap:16px">
        <span style="color:var(--text-dim)">tx</span><span class="val">${fmtNum(r.t[0], 4)} m</span>
      </div>
      <div style="display:flex;gap:16px">
        <span style="color:var(--text-dim)">ty</span><span class="val">${fmtNum(r.t[1], 4)} m</span>
      </div>
      <div style="display:flex;gap:16px">
        <span style="color:var(--text-dim)">tz</span><span class="val">${fmtNum(r.t[2], 4)} m</span>
      </div>
    </div>

    <div class="section-label">Rodrigues Vector</div>
    <div class="card" style="font-family:var(--mono);font-size:11px;line-height:2">
      [${r.rvec.map(v => fmtNum(v, 4)).join(", ")}]
    </div>

    <div class="section-label">Distance to Tag</div>
    <div class="card">
      <div style="font-size:20px;color:var(--accent-light);font-family:var(--mono);font-weight:500">
        ${fmtNum(Math.sqrt(r.t[0]**2 + r.t[1]**2 + r.t[2]**2) * 100, 1)} cm
      </div>
      <div style="font-size:11px;color:var(--text-dim);margin-top:4px">Euclidean distance from camera to tag center</div>
    </div>`;
  f.innerHTML = `
    <button class="btn" onclick="goStep(4)">← Recapture</button>
    <button class="btn primary" style="flex:1" onclick="goStep(6)">Hand-Eye Calibration →</button>
    <button class="btn" onclick="goStep(9)">Skip →</button>`;
}
