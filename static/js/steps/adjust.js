// ───────── ADJUST ─────────
function renderAdjust(c, f) {
  stopStream();
  startStream("undistort");
  updateCamDot(true);

  const cal = calibrationResult || {};
  const ext = extrinsicResult || {};
  const hasExt = !!extrinsicResult;

  function makeSlider(id, label, value, min, max, step, unit = "") {
    const pct = ((value - min) / (max - min)) * 100;
    const dec = step < 0.01 ? 6 : step < 1 ? 2 : 1;
    return `<div class="slider-group" id="sg-${id}">
      <div class="slider-header">
        <span class="lbl">${label}</span>
        <input class="val" id="sv-${id}" type="text" value="${fmtNum(value, dec)}${unit}"
          data-min="${min}" data-max="${max}" data-step="${step}" data-unit="${unit}" data-dec="${dec}"
          onchange="sliderValFromInput('${id}', this, ${min}, ${max}, ${step}, v => onSlider('${id}', v, ${min}, ${max}, ${step}))"
          onkeydown="if(event.key==='Enter'){this.blur()}" />
      </div>
      <div class="slider-track">
        <div class="bg"></div>
        <div class="fill" id="sf-${id}" style="width:${pct}%"></div>
        <input type="range" min="${min}" max="${max}" step="${step}" value="${value}"
          oninput="onSlider('${id}', this.value, ${min}, ${max}, ${step})" />
        <div class="thumb" id="st-${id}" style="left:calc(${pct}% - 6px)"></div>
      </div>
    </div>`;
  }

  c.innerHTML = `
    <div class="section-label">Manual Adjustment</div>
    <div class="hint">Fine-tune any parameter. The live feed shows the <em>undistorted</em> image in real time so you can see the effect of your changes.</div>

    <div class="section-label">Focal Length</div>
    ${makeSlider("fx", "fx", cal.fx || 800, 100, 3000, 1, " px")}
    ${makeSlider("fy", "fy", cal.fy || 800, 100, 3000, 1, " px")}

    <div class="divider"></div>
    <div class="section-label">Principal Point</div>
    ${makeSlider("cx", "cx", cal.cx || 320, 0, (cal.image_size?.[0] || 1280), 1, " px")}
    ${makeSlider("cy", "cy", cal.cy || 240, 0, (cal.image_size?.[1] || 720), 1, " px")}

    <div class="divider"></div>
    <div class="section-label">Radial Distortion</div>
    ${makeSlider("k1", "k1", cal.k1 || 0, -2, 2, 0.0001)}
    ${makeSlider("k2", "k2", cal.k2 || 0, -1, 1, 0.0001)}

    <div class="divider"></div>
    <div class="section-label">Tangential Distortion</div>
    ${makeSlider("p1", "p1", cal.p1 || 0, -0.1, 0.1, 0.00001)}
    ${makeSlider("p2", "p2", cal.p2 || 0, -0.1, 0.1, 0.00001)}

    ${hasExt ? `
    <div class="divider"></div>
    <div class="section-label">Extrinsic — Rodrigues (rotation)</div>
    ${makeSlider("rv0", "rvec[0]", ext.rvec[0], -3.15, 3.15, 0.001, " rad")}
    ${makeSlider("rv1", "rvec[1]", ext.rvec[1], -3.15, 3.15, 0.001, " rad")}
    ${makeSlider("rv2", "rvec[2]", ext.rvec[2], -3.15, 3.15, 0.001, " rad")}

    <div class="divider"></div>
    <div class="section-label">Extrinsic — Translation</div>
    ${makeSlider("tx", "tx", ext.t[0], -2, 2, 0.001, " m")}
    ${makeSlider("ty", "ty", ext.t[1], -2, 2, 0.001, " m")}
    ${makeSlider("tz", "tz", ext.t[2], 0, 5, 0.001, " m")}
    ` : ""}

    <div class="card" style="margin-top:16px;border-color:rgba(52,211,153,0.15)">
      <div style="font-size:12px;color:var(--green);line-height:1.6">
        <strong>Note:</strong> Adjustments are applied in real time. The undistorted feed updates as you move the sliders. Changes persist to the export.
      </div>
    </div>`;
  f.innerHTML = `
    <button class="btn" onclick="goStep(${handeyeResult ? 8 : hasExt ? 5 : 3})">← Back</button>
    <button class="btn primary" style="flex:1" onclick="goStep(10)">Export Results →</button>`;
}

// Debounced slider update
let _sliderTimeout = null;
window.onSlider = function(id, rawVal, min, max, step) {
  const val = parseFloat(rawVal);
  const pct = ((val - min) / (max - min)) * 100;
  const sv = document.getElementById("sv-" + id);
  const sf = document.getElementById("sf-" + id);
  const st = document.getElementById("st-" + id);
  const dec = step < 0.01 ? 6 : step < 1 ? 2 : 1;
  const unit = (id === "fx" || id === "fy" || id === "cx" || id === "cy") ? " px" : id.startsWith("rv") ? " rad" : (id === "tx" || id === "ty" || id === "tz") ? " m" : "";
  if (sv) sv.value = fmtNum(val, dec) + unit;
  if (sf) sf.style.width = pct + "%";
  if (st) st.style.left = `calc(${pct}% - 6px)`;

  clearTimeout(_sliderTimeout);
  _sliderTimeout = setTimeout(() => {
    // Determine which params changed
    const intrinsicKeys = ["fx","fy","cx","cy","k1","k2","p1","p2"];
    const extRvecKeys = ["rv0","rv1","rv2"];
    const extTKeys = ["tx","ty","tz"];

    if (intrinsicKeys.includes(id)) {
      const params = {};
      intrinsicKeys.forEach(k => {
        const el = document.querySelector(`#sg-${k} input[type=range]`);
        if (el) params[k] = parseFloat(el.value);
      });
      post("/api/adjust/intrinsic", params);
      if (calibrationResult) Object.assign(calibrationResult, params);
    } else if (extRvecKeys.includes(id) || extTKeys.includes(id)) {
      const rvec = [0,1,2].map(i => {
        const el = document.querySelector(`#sg-rv${i} input[type=range]`);
        return el ? parseFloat(el.value) : (extrinsicResult?.rvec?.[i] || 0);
      });
      const t = ["tx","ty","tz"].map(k => {
        const el = document.querySelector(`#sg-${k} input[type=range]`);
        return el ? parseFloat(el.value) : 0;
      });
      post("/api/adjust/extrinsic", { rvec, t });
      if (extrinsicResult) { extrinsicResult.rvec = rvec; extrinsicResult.t = t; }
    }
  }, 100);
}
