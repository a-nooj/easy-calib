// ═══════════════════════════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════════════════════════
const STEP_DEFS = [
  { id: "welcome",     label: "Welcome" },
  { id: "print",       label: "Print Boards" },
  { id: "capture",     label: "Capture" },
  { id: "intrinsic",   label: "Intrinsic" },
  { id: "ext-capture", label: "Tag Capture" },
  { id: "extrinsic",   label: "Extrinsic" },
  { id: "he-capture",  label: "Hand-Eye" },
  { id: "he-result",   label: "HE Result" },
  { id: "he-adjust",   label: "HE Adjust" },
  { id: "adjust",      label: "Adjust" },
  { id: "export",      label: "Export" },
];

let currentStep = 0;
let captures = [];        // thumbnail b64 strings
let calibrationResult = null;
let extrinsicResult = null;
let handeyePairs = [];    // {thumbnail, ee_pose}
let handeyeResult = null;
let statusPoll = null;
let lastStatus = {};
let activeTab = "calibrate";
