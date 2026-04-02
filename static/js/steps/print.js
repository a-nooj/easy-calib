// ───────── PRINT BOARDS ─────────
function renderPrint(c, f) {
  stopStream();
  $("#stream-img").style.display = "none";
  $("#placeholder").style.display = "flex";
  c.innerHTML = `
    <div class="section-label">Print Your Calibration Boards</div>
    <div class="hint">You need to print <strong>two targets</strong>. Click each button to download a high-resolution PNG. Print at <em>actual size</em> (no scaling) on a flat sheet.</div>

    <div class="card">
      <div style="font-size:13px;color:var(--text);margin-bottom:8px;font-weight:500">① ChArUco Board</div>
      <div style="font-size:12px;color:var(--text-dim);line-height:1.6;margin-bottom:10px">7×5 squares with ArUco markers. Used for intrinsic calibration. Mount on a rigid flat surface (cardboard, clipboard, etc).</div>
      <div class="print-preview"><img src="/api/board/charuco" alt="ChArUco board" /></div>
      <a href="/api/board/charuco" download="charuco_board.png" class="btn sm full" style="text-align:center;text-decoration:none;display:block">⬇ Download ChArUco Board</a>
    </div>

    <div class="card">
      <div style="font-size:13px;color:var(--text);margin-bottom:8px;font-weight:500">② AprilTag</div>
      <div style="font-size:12px;color:var(--text-dim);line-height:1.6;margin-bottom:10px">AprilTag 36h11 (ID #0). Used for extrinsic calibration. Print and place at a known location in your scene.</div>
      <div class="print-preview"><img src="/api/board/apriltag" alt="AprilTag" /></div>
      <a href="/api/board/apriltag" download="apriltag_36h11_id0.png" class="btn sm full" style="text-align:center;text-decoration:none;display:block">⬇ Download AprilTag</a>
    </div>

    <div class="divider"></div>
    <div class="section-label">Dimensions</div>
    <div class="hint">After printing, <strong>measure</strong> your printed squares and enter the real size below. This is critical for metric accuracy.</div>
    <div style="display:flex;gap:10px;margin-bottom:10px">
      <div style="flex:1">
        <label style="font-size:10px;font-family:var(--mono);color:var(--text-dim);display:block;margin-bottom:4px">ChArUco square (mm)</label>
        <input id="sq-size" type="number" value="30" min="5" max="200" step="0.1"
          style="width:100%;padding:8px 10px;border-radius:6px;border:1px solid var(--border2);background:var(--panel2);color:var(--text);font-family:var(--mono);font-size:13px" />
      </div>
      <div style="flex:1">
        <label style="font-size:10px;font-family:var(--mono);color:var(--text-dim);display:block;margin-bottom:4px">AprilTag size (mm)</label>
        <input id="tag-size" type="number" value="50" min="5" max="500" step="0.1"
          style="width:100%;padding:8px 10px;border-radius:6px;border:1px solid var(--border2);background:var(--panel2);color:var(--text);font-family:var(--mono);font-size:13px" />
      </div>
    </div>
    <div class="card" style="border-color:rgba(251,191,36,0.15)">
      <div style="font-size:12px;color:var(--amber);line-height:1.6">
        <strong>Important:</strong> Many printers scale images. Measure the actual printed size with a ruler and enter it above. Even 1 mm error affects accuracy.
      </div>
    </div>`;
  f.innerHTML = `
    <button class="btn" onclick="goStep(0)">← Back</button>
    <button class="btn primary" style="flex:1" onclick="startCapturing()">Boards Printed — Start Camera →</button>`;
}

window.startCapturing = function() {
  captures = [];
  post("/api/capture/clear");
  goStep(2);
  startStream("charuco");
  updateCamDot(true);
}
