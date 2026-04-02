// ───────── HAND-EYE CAPTURE (touch-point only) ─────────
function renderHECapture(c, f) {
  startStream("handeye");
  updateCamDot(true);
  const tagMM = document.getElementById('tag-size')?.value || document.getElementById('ext-tag-size')?.value || 50;
  post("/api/handeye/config", { tag_size: parseFloat(tagMM) / 1000 });

  c.innerHTML = `
    <div class="section-label">Touch-Point Calibration</div>
    <div class="hint">The camera is <strong>fixed</strong> and observes the workspace. The robot physically <strong>touches the center of the AprilTag</strong> with its calibrated TCP. This gives direct 3D point correspondences — <em>no rotation needed</em>.</div>

    <div style="font-family:var(--mono);font-size:10px;color:var(--text-dim);line-height:1.8;padding:8px 12px;background:rgba(74,124,255,0.04);border-radius:6px;margin-bottom:12px">
      <span style="color:var(--green)">Fixed Camera</span> → observes → <span style="color:var(--accent-light)">AprilTag (fixed)</span> ← touched by ← <span style="color:var(--amber)">Robot TCP</span>
    </div>

    <div class="card" style="border-color:rgba(74,124,255,0.15)">
      <div style="font-size:12px;color:var(--accent-light);line-height:1.7">
        <strong>Procedure:</strong><br>
        1. Place the AprilTag flat on a surface the robot can reach<br>
        2. Jog the robot so the <strong>TCP touches the tag center</strong><br>
        3. Read the <strong>TCP position</strong> (x, y, z only) from the controller<br>
        4. Enter it below and click <em>Add Point</em><br>
        5. Move the tag to a <strong>new location</strong> and repeat<br>
        6. Collect ≥ 3 points — use <strong>different heights</strong> (non-coplanar) for best results
      </div>
    </div>
    <div class="hint" style="margin-top:10px;font-size:11px">Solves for <strong>T<sub>cam←base</sub></strong> via SVD point registration (Procrustes).</div>

    <div class="section-label">TCP Position (meters)</div>
    <div class="hint">Enter the robot's <strong>tool center point position</strong> from your controller. Only translation — no rotation needed.</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:14px">
      <div>
        <label style="font-size:9px;font-family:var(--mono);color:var(--text-micro);display:block;margin-bottom:3px">X (m)</label>
        <input id="ee-x" type="number" value="0" step="0.001" style="width:100%;padding:6px 8px;border-radius:5px;border:1px solid var(--border2);background:var(--panel2);color:var(--text);font-family:var(--mono);font-size:12px" />
      </div>
      <div>
        <label style="font-size:9px;font-family:var(--mono);color:var(--text-micro);display:block;margin-bottom:3px">Y (m)</label>
        <input id="ee-y" type="number" value="0" step="0.001" style="width:100%;padding:6px 8px;border-radius:5px;border:1px solid var(--border2);background:var(--panel2);color:var(--text);font-family:var(--mono);font-size:12px" />
      </div>
      <div>
        <label style="font-size:9px;font-family:var(--mono);color:var(--text-micro);display:block;margin-bottom:3px">Z (m)</label>
        <input id="ee-z" type="number" value="0" step="0.001" style="width:100%;padding:6px 8px;border-radius:5px;border:1px solid var(--border2);background:var(--panel2);color:var(--text);font-family:var(--mono);font-size:12px" />
      </div>
    </div>

    <button class="btn full" id="he-add-btn" onclick="addHEPair()" style="margin-bottom:14px">📍 Add Point</button>

    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
      <span class="badge ${handeyePairs.length >= 3 ? 'green' : 'amber'}" id="he-pair-badge">${handeyePairs.length} / 3+ points</span>
      <span class="badge blue" id="he-tag-badge">—</span>
    </div>
    <div class="progress-bar"><div class="fill" id="he-progress" style="width:${Math.min(100, (handeyePairs.length / 3) * 100)}%"></div></div>

    <div class="captures-grid" id="he-grid"></div>

    <div id="he-feedback" style="font-size:12px;color:var(--text-dim);text-align:center;min-height:20px"></div>

    <div class="card" style="border-color:rgba(251,191,36,0.15);margin-top:10px">
      <div style="font-size:12px;color:var(--amber);line-height:1.6">
        <strong>Tips for accuracy:</strong><br>
        • Your robot's <strong>TCP must be calibrated</strong> — accuracy depends entirely on it<br>
        • Spread points across the workspace — <strong>avoid a straight line</strong><br>
        • Use <strong>different Z heights</strong> (e.g. tag on table, tag on a box) to avoid coplanar degeneracy<br>
        • 4–6 well-spread points is usually sufficient<br>
        • The tag can move between captures — just touch its center each time
      </div>
    </div>`;
  renderHEGrid();
  f.innerHTML = `
    <button class="btn" onclick="goStep(5)">← Back</button>
    <button class="btn danger sm" onclick="clearHEPairs()">Clear</button>
    <button class="btn primary" style="flex:1" id="he-cal-btn" ${handeyePairs.length < 3 ? 'disabled' : ''} onclick="runHECalibration()">Calibrate Hand-Eye →</button>`;

  // Live tag status updater
  if (!window._heInterval) {
    window._heInterval = setInterval(() => {
      if (currentStep !== 6) { clearInterval(window._heInterval); window._heInterval = null; return; }
      const b = document.getElementById("he-tag-badge");
      if (b && lastStatus.apriltag_detected !== undefined) {
        b.textContent = lastStatus.apriltag_detected ? "✓ Tag visible" : "No tag";
        b.className = "badge " + (lastStatus.apriltag_detected ? "green" : "red");
      }
    }, 300);
  }
}

function renderHEGrid() {
  const grid = document.getElementById("he-grid");
  if (!grid) return;
  grid.innerHTML = handeyePairs.map((p, i) =>
    `<div class="capture-thumb"><img src="data:image/jpeg;base64,${p.thumbnail}" /><div class="idx">#${i + 1}</div></div>`
  ).join("");
}

window.addHEPair = async function() {
  const btn = document.getElementById("he-add-btn");
  const fb = document.getElementById("he-feedback");
  btn.disabled = true;
  btn.textContent = "Capturing…";
  const vals = ["ee-x","ee-y","ee-z"].map(id => parseFloat(document.getElementById(id)?.value || 0));
  const r = await post("/api/touchpoint/pair", { tcp_pos: vals });
  btn.disabled = false;
  btn.textContent = "📍 Add Point";

  if (r.ok) {
    handeyePairs.push({ thumbnail: r.thumbnail });
    toast(`Point #${r.num_pairs} added`);
    fb.style.color = "var(--green)"; fb.textContent = `Point #${r.num_pairs} saved`;
    renderHEGrid();
    const p = document.getElementById("he-progress");
    if (p) p.style.width = Math.min(100, (handeyePairs.length / 3) * 100) + "%";
    const b = document.getElementById("he-pair-badge");
    if (b) { b.textContent = `${handeyePairs.length} / 3+ points`; b.className = "badge " + (handeyePairs.length >= 3 ? "green" : "amber"); }
    const cb = document.getElementById("he-cal-btn");
    if (cb && handeyePairs.length >= 3) cb.disabled = false;
  } else {
    toast(r.error || "Failed to add", false);
    fb.style.color = "var(--red)"; fb.textContent = r.error || "Failed — ensure tag is visible";
  }
}

window.clearHEPairs = function() {
  handeyePairs = [];
  handeyeResult = null;
  post("/api/handeye/clear");
  renderHECapture($("#sidebar-content"), $("#sidebar-footer"));
}

window.runHECalibration = async function() {
  const c = $("#sidebar-content");
  c.innerHTML = `
    <div class="section-label">Computing Point Registration…</div>
    <div class="hint">Running SVD rigid body registration (Procrustes) on ${handeyePairs.length} point correspondences.</div>
    <div style="text-align:center;padding:40px"><div class="badge blue">⏳ Computing…</div></div>`;

  const r = await post("/api/calibrate/touchpoint");

  if (r.ok) {
    handeyeResult = r.result;
    toast(`Calibrated — ${r.result.method} (RMSE: ${r.result.rmse_mm} mm)`);
    goStep(7);
  } else {
    toast(r.error || "Calibration failed", false);
    c.innerHTML = `
      <div class="section-label" style="color:var(--red)">Calibration Failed</div>
      <div class="hint">${r.error || "Unknown error"}. Ensure you have ≥ 3 non-collinear points at different heights.</div>`;
    $("#sidebar-footer").innerHTML = `<button class="btn full" onclick="goStep(6)">← Back to Capture</button>`;
  }
}

// ───────── HAND-EYE RESULT ─────────
function renderHEResult(c, f) {
  if (!handeyeResult) { goStep(6); return; }
  const r = handeyeResult;
  // Keep handeye stream running so tag overlay is visible
  startStream("handeye");
  updateCamDot(true);

  c.innerHTML = `
    <div class="section-label">Touch-Point Registration Result</div>
    <div class="hint">Transform computed via <strong>${r.method}</strong> using ${r.num_pairs} point correspondences. The live feed shows the derived frame projected onto the tag.</div>

    <div style="display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap">
      <span class="badge green">${r.method}</span>
      <span class="badge blue">${r.config}</span>
      <span class="badge ${(r.rmse_mm||0) < 3 ? 'green' : (r.rmse_mm||0) < 10 ? 'amber' : 'red'}">RMSE: ${r.rmse_mm || fmtNum(r.residual*1000, 3)} mm</span>
    </div>

    ${(r.warning) ? `
    <div class="card" style="border-color:rgba(248,113,113,0.2);margin-bottom:14px">
      <div style="font-size:12px;color:var(--red);line-height:1.6">
        <strong>⚠ Warning:</strong> ${r.warning}
      </div>
    </div>` : ''}

    <div class="section-label">Rotation Matrix R</div>
    <div class="matrix">
      ${r.R.map(row => `<div style="display:flex;justify-content:space-between">${row.map(v => `<span class="val" style="width:33%">${fmtNum(v, 5)}</span>`).join("")}</div>`).join("")}
    </div>

    <div class="section-label">Translation Vector t</div>
    <div class="matrix">
      <div style="display:flex;gap:16px"><span style="color:var(--text-dim)">tx</span><span class="val">${fmtNum(r.t[0], 5)} m</span></div>
      <div style="display:flex;gap:16px"><span style="color:var(--text-dim)">ty</span><span class="val">${fmtNum(r.t[1], 5)} m</span></div>
      <div style="display:flex;gap:16px"><span style="color:var(--text-dim)">tz</span><span class="val">${fmtNum(r.t[2], 5)} m</span></div>
    </div>

    <div class="section-label">Rodrigues Vector</div>
    <div class="card" style="font-family:var(--mono);font-size:11px;line-height:2">
      [${r.rvec.map(v => fmtNum(v, 5)).join(", ")}]
    </div>

    <div class="section-label">Point-by-Point Error</div>
    <div class="card" style="font-family:var(--mono);font-size:10px;line-height:1.8">
      ${(r.per_point_errors_mm || []).map((e, i) =>
        `<div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Point ${i+1}</span><span style="color:${e < 3 ? 'var(--green)' : e < 10 ? 'var(--amber)' : 'var(--red)'}">${e} mm</span></div>`
      ).join("")}
      <div style="height:1px;background:var(--border);margin:6px 0"></div>
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">RMSE</span><span style="color:var(--green)">${r.rmse_mm} mm</span></div>
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Max error</span><span>${r.max_error_mm} mm</span></div>
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Collinearity</span><span style="color:${(r.collinearity_score||0) < 0.05 ? 'var(--red)' : 'var(--green)'}">${fmtNum(r.collinearity_score, 4)} ${(r.collinearity_score||0) < 0.05 ? '⚠ coplanar' : '✓'}</span></div>
    </div>

    <div class="card" style="border-color:rgba(52,211,153,0.15)">
      <div style="font-size:12px;color:var(--green);line-height:1.6">
        <strong>Live overlay:</strong> The yellow frame on the video shows the registration transform composed with the tag pose. If it looks wrong, proceed to the adjustment step to tune it.
      </div>
    </div>`;
  f.innerHTML = `
    <button class="btn" onclick="goStep(6)">← Recapture</button>
    <button class="btn primary" style="flex:1" onclick="goStep(8)">Adjust Transform →</button>`;
}

// ───────── HAND-EYE ADJUST ─────────
function renderHEAdjust(c, f) {
  if (!handeyeResult) { goStep(6); return; }
  const r = handeyeResult;
  startStream("handeye");
  updateCamDot(true);

  function makeSlider(id, label, value, min, max, step, unit = "") {
    const pct = ((value - min) / (max - min)) * 100;
    const dec = step < 0.01 ? 5 : step < 1 ? 3 : 1;
    return `<div class="slider-group" id="sg-${id}">
      <div class="slider-header">
        <span class="lbl">${label}</span>
        <input class="val" id="sv-${id}" type="text" value="${fmtNum(value, dec)}${unit}"
          data-min="${min}" data-max="${max}" data-step="${step}" data-unit="${unit}" data-dec="${dec}"
          onchange="sliderValFromInput('${id}', this, ${min}, ${max}, ${step}, v => onHESlider('${id}', v, ${min}, ${max}, ${step}))"
          onkeydown="if(event.key==='Enter'){this.blur()}" />
      </div>
      <div class="slider-track">
        <div class="bg"></div>
        <div class="fill" id="sf-${id}" style="width:${pct}%"></div>
        <input type="range" min="${min}" max="${max}" step="${step}" value="${value}"
          oninput="onHESlider('${id}', this.value, ${min}, ${max}, ${step})" />
        <div class="thumb" id="st-${id}" style="left:calc(${pct}% - 6px)"></div>
      </div>
    </div>`;
  }

  c.innerHTML = `
    <div class="section-label">Adjust Hand-Eye Transform</div>
    <div class="hint">Fine-tune the hand-eye transform while watching the <em>live overlay</em>. The yellow frame should align with the physical relationship between camera and end-effector.</div>

    <div class="section-label">Rotation (Rodrigues)</div>
    ${makeSlider("he-rv0", "rvec[0]", r.rvec[0], -3.15, 3.15, 0.001, " rad")}
    ${makeSlider("he-rv1", "rvec[1]", r.rvec[1], -3.15, 3.15, 0.001, " rad")}
    ${makeSlider("he-rv2", "rvec[2]", r.rvec[2], -3.15, 3.15, 0.001, " rad")}

    <div class="divider"></div>
    <div class="section-label">Translation</div>
    ${makeSlider("he-tx", "tx", r.t[0], -1, 1, 0.0005, " m")}
    ${makeSlider("he-ty", "ty", r.t[1], -1, 1, 0.0005, " m")}
    ${makeSlider("he-tz", "tz", r.t[2], -1, 1, 0.0005, " m")}

    <div class="divider"></div>
    <div class="section-label">Live Diagnostics</div>
    <div class="card" style="font-family:var(--mono);font-size:10px;line-height:1.8" id="he-diag">
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Method</span><span>${r.method}</span></div>
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">Config</span><span>${r.config}</span></div>
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">||t||</span><span id="he-dist">${fmtNum(Math.sqrt(r.t[0]**2+r.t[1]**2+r.t[2]**2)*1000, 1)} mm</span></div>
    </div>

    <div class="card" style="border-color:rgba(52,211,153,0.15)">
      <div style="font-size:12px;color:var(--green);line-height:1.6">
        <strong>What to look for:</strong> Move the robot around — the projected yellow frame should remain consistent relative to the tag. If it drifts or flips, adjust rotation. If offset is wrong, adjust translation.
      </div>
    </div>`;
  f.innerHTML = `
    <button class="btn" onclick="goStep(7)">← Back</button>
    <button class="btn primary" style="flex:1" onclick="goStep(9)">Continue to Final Adjust →</button>`;
}

let _heSliderTimeout = null;
window.onHESlider = function(id, rawVal, min, max, step) {
  const val = parseFloat(rawVal);
  const pct = ((val - min) / (max - min)) * 100;
  const sv = document.getElementById("sv-" + id);
  const sf = document.getElementById("sf-" + id);
  const st = document.getElementById("st-" + id);
  const unit = id.startsWith("he-rv") ? " rad" : " m";
  const dec = step < 0.01 ? 5 : step < 1 ? 3 : 1;
  if (sv) sv.value = fmtNum(val, dec) + unit;
  if (sf) sf.style.width = pct + "%";
  if (st) st.style.left = `calc(${pct}% - 6px)`;

  clearTimeout(_heSliderTimeout);
  _heSliderTimeout = setTimeout(() => {
    const rvec = [0,1,2].map(i => {
      const el = document.querySelector(`#sg-he-rv${i} input[type=range]`);
      return el ? parseFloat(el.value) : (handeyeResult?.rvec?.[i] || 0);
    });
    const t = ["he-tx","he-ty","he-tz"].map(k => {
      const el = document.querySelector(`#sg-${k} input[type=range]`);
      return el ? parseFloat(el.value) : 0;
    });
    post("/api/adjust/handeye", { rvec, t });
    if (handeyeResult) { handeyeResult.rvec = rvec; handeyeResult.t = t; }

    // Update distance display
    const d = document.getElementById("he-dist");
    if (d) d.textContent = fmtNum(Math.sqrt(t[0]**2+t[1]**2+t[2]**2)*1000, 1) + " mm";
  }, 80);
}
