// ───────── CAMERA PICKER ─────────
// selectedCameraIndex is kept in sync with backend state["camera_index"]
window.selectedCameraIndex = 0;

window.openCameraPicker = async function(onSelect) {
  window._camPickerOnSelect = onSelect || null;
  document.getElementById('cam-modal-overlay').style.display = 'flex';
  await _loadCameras();
};

window.closeCameraPicker = function() {
  document.getElementById('cam-modal-overlay').style.display = 'none';
};

window.rescanCameras = async function() {
  await _loadCameras();
};

async function _loadCameras() {
  const grid = document.getElementById('cam-grid');
  const subtitle = document.getElementById('cam-modal-subtitle');
  if (!grid) return;

  grid.innerHTML = '<div class="cam-scanning">Scanning…</div>';
  subtitle.textContent = 'Scanning for connected cameras…';

  const r = await api('/api/cameras');

  if (!r.ok) {
    subtitle.textContent = r.error || 'Scan failed';
    grid.innerHTML = `<div class="cam-scanning" style="color:var(--red)">${r.error || 'Could not scan cameras. Stop the stream first.'}</div>`;
    return;
  }

  if (r.cameras.length === 0) {
    subtitle.textContent = 'No cameras found';
    grid.innerHTML = '<div class="cam-scanning">No cameras detected. Check connections and try rescanning.</div>';
    return;
  }

  subtitle.textContent = `${r.cameras.length} camera${r.cameras.length > 1 ? 's' : ''} found — select one to use`;

  grid.innerHTML = r.cameras.map(cam => `
    <div class="cam-card ${cam.index === window.selectedCameraIndex ? 'selected' : ''}" id="cam-card-${cam.index}">
      <div class="cam-card-preview">
        <img id="cam-preview-${cam.index}" style="display:none" alt="Camera ${cam.index} preview" />
        <span class="cam-preview-loading" id="cam-loading-${cam.index}">Loading…</span>
      </div>
      <div class="cam-card-info">
        <div class="cam-card-name">Camera ${cam.index}</div>
        <div class="cam-card-res">${cam.width}×${cam.height}</div>
      </div>
      <button class="cam-card-select" onclick="pickCamera(${cam.index})">
        ${cam.index === window.selectedCameraIndex ? '✓ Active' : 'Select →'}
      </button>
    </div>
  `).join('');

  // Load previews asynchronously so the cards appear immediately
  for (const cam of r.cameras) {
    const img = document.getElementById(`cam-preview-${cam.index}`);
    const lbl = document.getElementById(`cam-loading-${cam.index}`);
    if (!img) continue;
    img.onload = () => {
      img.style.display = 'block';
      if (lbl) lbl.style.display = 'none';
    };
    img.onerror = () => {
      if (lbl) lbl.textContent = 'No preview';
    };
    // Cache-bust so rescans get a fresh frame
    img.src = `/api/camera/preview/${cam.index}?t=${Date.now()}`;
  }
}

window.pickCamera = async function(index) {
  const r = await post('/api/camera/select', { index });
  if (!r.ok) {
    toast(r.error || 'Could not select camera', false);
    return;
  }
  window.selectedCameraIndex = index;
  // Update camera status text
  const txt = document.getElementById('cam-status-text');
  if (txt && !txt.textContent.includes('on')) {
    txt.textContent = `Camera ${index} off`;
  }
  closeCameraPicker();
  toast(`Camera ${index} selected`);
  if (window._camPickerOnSelect) {
    window._camPickerOnSelect(index);
    window._camPickerOnSelect = null;
  }
};
