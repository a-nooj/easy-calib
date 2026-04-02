// ═══════════════════════════════════════════════════════════════
//  STREAM + STATUS POLL
// ═══════════════════════════════════════════════════════════════
function startStatusPoll() {
  if (statusPoll) return;
  statusPoll = setInterval(async () => {
    lastStatus = await api("/api/status");
  }, 250);
}

function stopStatusPoll() {
  if (statusPoll) { clearInterval(statusPoll); statusPoll = null; }
}

function startStream(mode) {
  post("/api/mode", { mode });
  const img = $("#stream-img");
  img.src = "/api/stream?" + Date.now();
  img.style.display = "block";
  $("#placeholder").style.display = "none";
  startStatusPoll();
}

function stopStream() {
  const img = $("#stream-img");
  img.src = "";
  img.style.display = "none";
  post("/api/stream/stop");
  post("/api/mode", { mode: "idle" });
  stopStatusPoll();
}

function updateCamDot(on) {
  $("#cam-dot").className = "status-dot " + (on ? "on" : "off");
  $("#cam-status-text").textContent = on ? "Camera active" : "Camera off";
}
