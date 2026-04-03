// ───────── WELCOME ─────────
function renderWelcome(c, f) {
  stopStream();
  $("#stream-img").style.display = "none";
  $("#placeholder").style.display = "flex";
  c.innerHTML = `
    <div class="section-label">Welcome</div>
    <div class="hint">This tool will guide you through <strong>full camera calibration</strong> in two stages:</div>
    <div class="card">
      <div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:12px">
        <span class="badge blue" style="flex-shrink:0">Step 1</span>
        <div>
          <div style="font-size:13px;color:var(--text);margin-bottom:4px;font-weight:500">Intrinsic Calibration</div>
          <div style="font-size:12px;color:var(--text-dim);line-height:1.6">Using a <em>ChArUco board</em>, we'll estimate your camera's focal length, principal point, and lens distortion.</div>
        </div>
      </div>
      <div style="display:flex;gap:12px;align-items:flex-start">
        <span class="badge blue" style="flex-shrink:0">Step 2</span>
        <div>
          <div style="font-size:13px;color:var(--text);margin-bottom:4px;font-weight:500">Extrinsic Calibration</div>
          <div style="font-size:12px;color:var(--text-dim);line-height:1.6">Using an <em>AprilTag</em> with known position, we'll solve for your camera's 6-DOF pose in the world.</div>
        </div>
      </div>
      <div style="height:1px;background:var(--border);margin:12px 0"></div>
      <div style="display:flex;gap:12px;align-items:flex-start">
        <span class="badge blue" style="flex-shrink:0">Step 3</span>
        <div>
          <div style="font-size:13px;color:var(--text);margin-bottom:4px;font-weight:500">Touch-Point Calibration <span style="font-size:10px;color:var(--text-micro);font-weight:400">(optional)</span></div>
          <div style="font-size:12px;color:var(--text-dim);line-height:1.6">If your camera observes a robot workspace, we'll compute the camera ↔ robot transform via <em>touch-point registration</em> (SVD Procrustes). Physically touch the AprilTag center with the robot TCP — no rotation input needed.</div>
        </div>
      </div>
    </div>
    <div class="divider"></div>
    <div class="section-label">What you'll need</div>
    <div class="hint">
      <strong>1.</strong> A printer (we'll generate the boards for you)<br>
      <strong>2.</strong> A flat surface to mount the ChArUco board<br>
      <strong>3.</strong> A ruler or tape measure (to enter real dimensions)<br>
      <strong>4.</strong> Your camera connected to this computer<br>
      <strong>5.</strong> <em>Optional:</em> Robot with accessible EE pose readout (for hand-eye calibration)
    </div>
    <div class="card" style="border-color:rgba(52,211,153,0.15)">
      <div style="font-size:12px;color:var(--green);line-height:1.6">
        <strong>Tip:</strong> For best results, capture the board from many angles and distances — fill different parts of the frame. We need at least 4 views, but 8–12 is better.
      </div>
    </div>`;
  f.innerHTML = `<button class="btn primary full" onclick="openCameraPicker(() => goStep(1))">Let's Begin →</button>`;
}
