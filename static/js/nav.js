// ═══════════════════════════════════════════════════════════════
//  STEP BAR + NAVIGATION
// ═══════════════════════════════════════════════════════════════
function renderStepBar() {
  const bar = $("#step-bar");
  bar.innerHTML = "";
  STEP_DEFS.forEach((s, i) => {
    if (i > 0) { const sep = document.createElement("div"); sep.className = "step-sep"; bar.appendChild(sep); }
    const el = document.createElement("div");
    el.className = "step-item" + (i === currentStep ? " active" : "") + (i < currentStep ? " done" : "");
    el.innerHTML = `<div class="step-num">${i < currentStep ? "✓" : i + 1}</div><div class="step-label">${s.label}</div>`;
    el.onclick = () => { if (i <= currentStep) goStep(i); };
    el.style.cursor = i <= currentStep ? "pointer" : "default";
    bar.appendChild(el);
  });
}

window.goStep = function(idx) {
  currentStep = idx;
  renderStepBar();
  const content = $("#sidebar-content");
  const footer = $("#sidebar-footer");
  content.innerHTML = "";
  footer.innerHTML = "";

  switch (STEP_DEFS[idx].id) {
    case "welcome":     renderWelcome(content, footer); break;
    case "print":       renderPrint(content, footer); break;
    case "capture":     renderCapture(content, footer); break;
    case "intrinsic":   renderIntrinsic(content, footer); break;
    case "ext-capture": renderExtCapture(content, footer); break;
    case "extrinsic":   renderExtrinsic(content, footer); break;
    case "he-capture":  renderHECapture(content, footer); break;
    case "he-result":   renderHEResult(content, footer); break;
    case "he-adjust":   renderHEAdjust(content, footer); break;
    case "adjust":      renderAdjust(content, footer); break;
    case "export":      renderExport(content, footer); break;
  }
  content.classList.add("fade-in");
}

// ═══════════════════════════════════════════════════════════════
//  TOP-LEVEL TAB SWITCHING
// ═══════════════════════════════════════════════════════════════
window.switchTab = function(tab) {
  if (tab === activeTab) return;

  // Clean up previous tab
  if (activeTab === "debug") {
    if (_debugStreamActive) {
      stopStream();
      _debugStreamActive = false;
      updateCamDot(false);
    }
    stopDebugMetricsPoll();
  } else if (activeTab === "evaluate") {
    evalCleanup();
    $("#evaluate-area").style.display = "none";
  }

  activeTab = tab;

  // Update tab button styles
  document.querySelectorAll(".top-tab").forEach(t => {
    t.classList.toggle("active", t.dataset.tab === tab);
  });

  const stepBar = $("#step-bar");

  if (tab === "calibrate") {
    stepBar.style.display = "flex";
    goStep(currentStep);
  } else if (tab === "evaluate") {
    stopStream();
    stepBar.style.display = "none";
    renderEvaluatePanel();
  } else {
    // Debug & Tune mode
    stopStream();
    stepBar.style.display = "none";
    $("#stream-img").style.display = "none";
    $("#placeholder").style.display = "flex";
    renderDebugPanel();
  }
}

// ═══════════════════════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════════════════════
goStep(0);
