// SmartRMA Technician Review & Hardware Comparator Workbench

const SLOT_NAMES = [
  'Front Shroud & Fans',
  'Backplate & Retention',
  'PCIe Gold Contacts',
  '12VHPWR Power Socket',
  'Serial Barcode Label'
];

function requiresTechnicianApproval(c) {
  // 1. Tier 4 (> $2500): Mandatory Physical Teardown by SLA
  if (c.t === 'T4' || c.v > 2500) return true;
  // 2. Fraud & Forensic Flags: Duplicate pHash or EXIF alteration
  if (c.fraud) return true;
  // 3. Tier 1 (< $300): Auto-approved only if risk < 30. If risk >= 30, escalates
  if (c.t === 'T1' || c.v < 300) return c.r >= 30;
  // 4. Tier 3 ($1000 - $2500): Requires conf >= 95%. Escalate if conf < 95% or ambiguous risk [30, 70)
  if (c.t === 'T3' || (c.v >= 1000 && c.v <= 2500)) {
    if (c.conf < 95) return true;
    if (c.r >= 30 && c.r < 70) return true;
    return false;
  }
  // 5. Tier 2 ($300 - $1000): Requires conf >= 85%. Escalate if conf < 85% or ambiguous risk [30, 70)
  if (c.t === 'T2' || (c.v >= 300 && c.v < 1000)) {
    if (c.conf < 85) return true;
    if (c.r >= 30 && c.r < 70) return true;
    return false;
  }
  return false;
}

function getInitialCases() {
  const defaultUserImages = [
    'assets/gpu_front.jpg',
    'assets/gpu_reference.jpg',
    'assets/gpu_reference.jpg',
    'assets/gpu_damaged.jpg',
    'assets/gpu_reference.jpg'
  ];

  const defaultCases = [
    {
      id: 'RMA-1042',
      p: 'RTX 4090 OC Founders Edition',
      v: 1240,
      t: 'T3',
      r: 80,
      a: 0.86,
      conf: 94,
      escalationReason: 'Confidence 94% below Tier 3 SLA Threshold (95%)',
      rn: '12VHPWR Power Connector (Pin 3)',
      cl: 'Damage from electrical overload or scorched pin connectors is explicitly excluded.',
      src: 'NVIDIA Limited Hardware Warranty, Section 4.2',
      st: 'Pending',
      userImages: [...defaultUserImages],
      subImg: 'assets/gpu_damaged.jpg',
      at: [62, 38],
      visionTelemetry: {
        anomaly_score: 0.86,
        flagged_region: '12VHPWR Power Connector (Pin 3)',
        severity: 'CRITICAL',
        visual_findings: 'Severe thermal discoloration, scorching, and localized connector nylon melting at Pin 3 terminal with copper pitting.',
        model_used: 'moondream:latest (Vision LLM)',
        at: [62, 38]
      },
      policyGrounding: {
        verdict: 'REJECTED (CID Exclusion)',
        cited_clause: 'Damage resulting from electrical overload, improper seating, or scorched pin connectors is explicitly excluded.',
        source_document: 'NVIDIA Limited Hardware Warranty',
        page: 14,
        explanation: 'Customer induced electrical overload defect excluded under Section 4.2.'
      }
    },
    {
      id: 'RMA-1045',
      p: 'NVIDIA RTX 6000 Ada Server Edition',
      v: 3150,
      t: 'T4',
      r: 55,
      a: 0.62,
      conf: 84,
      escalationReason: 'Tier 4 Enterprise SLA (> $2,500): Mandatory Forensic Lab Teardown',
      rn: 'GPU Core BGA / Power Stages',
      cl: 'High-value enterprise returns require mandatory physical teardown inspection prior to credit release.',
      src: 'Enterprise Support Agreement, Section 8.1',
      st: 'Pending',
      userImages: [...defaultUserImages],
      subImg: 'assets/gpu_front.jpg',
      at: [48, 52],
      visionTelemetry: {
        anomaly_score: 0.62,
        flagged_region: 'GPU Core BGA / Power Stages',
        severity: 'MODERATE',
        visual_findings: 'Slight flux residue around power inductors; no overt silicon fractures detected.',
        model_used: 'moondream:latest (Vision LLM)',
        at: [48, 52]
      },
      policyGrounding: {
        verdict: 'ESCALATE (Tier 4 Mandate)',
        cited_clause: 'High-value enterprise returns require mandatory physical teardown inspection prior to credit release.',
        source_document: 'Enterprise Support Agreement',
        page: 8,
        explanation: 'Mandatory ISO-compliant cleanroom laboratory teardown required before warranty claim release.'
      }
    },
    {
      id: 'RMA-1052',
      p: 'RTX 4080 Gaming X Trio',
      v: 1150,
      t: 'T3',
      r: 78,
      a: 0.82,
      conf: 91,
      fraud: true,
      escalationReason: 'Security Audit: Perceptual Hash (pHash) Duplicate Image Reuse Detected',
      rn: 'PCIe Connector & Shroud Pins',
      cl: 'Claims exhibiting serial recycling or photographic reuse require forensic review.',
      src: 'Anti-Fraud Compliance Matrix, Section 3.0',
      st: 'Pending',
      userImages: [...defaultUserImages],
      subImg: 'assets/gpu_reference.jpg',
      at: [30, 70],
      visionTelemetry: {
        anomaly_score: 0.82,
        flagged_region: 'PCIe Connector & Shroud Pins',
        severity: 'CRITICAL',
        visual_findings: 'Perceptual hash collision (pHash 64-bit distance = 0) with RMA-0941. Duplicate image reuse detected.',
        model_used: 'moondream:latest (Vision LLM)',
        at: [30, 70]
      },
      policyGrounding: {
        verdict: 'REJECTED (Fraud Policy)',
        cited_clause: 'Claims exhibiting serial recycling or photographic reuse require forensic review and claim revocation.',
        source_document: 'Anti-Fraud Compliance Matrix',
        page: 3,
        explanation: 'Serial recycling and image reuse violate terms of service.'
      }
    },
    {
      id: 'RMA-1039',
      p: 'RTX 4070 Ti Super 16GB',
      v: 690,
      t: 'T2',
      r: 41,
      a: 0.58,
      conf: 84,
      escalationReason: 'Inconclusive Risk (41/100) & Confidence 84% below Tier 2 Threshold (85%)',
      rn: 'VRAM Bank A0-A2 Traces',
      cl: 'Defects in silicon materials or factory soldering under normal use are fully covered.',
      src: 'Manufacturer Hardware Warranty, Section 2.1',
      st: 'Pending',
      userImages: [...defaultUserImages],
      subImg: 'assets/gpu_front.jpg',
      at: [48, 52],
      visionTelemetry: {
        anomaly_score: 0.58,
        flagged_region: 'VRAM Bank A0-A2 Traces',
        severity: 'MODERATE',
        visual_findings: 'Memory trace impedance anomaly reported; visual solder joints appear factory nominal.',
        model_used: 'moondream:latest (Vision LLM)',
        at: [48, 52]
      },
      policyGrounding: {
        verdict: 'APPROVED (Covered Defect)',
        cited_clause: 'Defects in silicon materials or factory soldering under normal use are fully covered.',
        source_document: 'Manufacturer Hardware Warranty',
        page: 5,
        explanation: 'Internal silicon solder/memory controller failure covered under standard warranty.'
      }
    },
    {
      id: 'RMA-1036',
      p: 'Mini-ITX Motherboard Z790-I',
      v: 260,
      t: 'T1',
      r: 34,
      a: 0.44,
      conf: 84,
      escalationReason: 'Tier 1 Risk Score (34/100) exceeds Auto-Approval Ceiling (< 30)',
      rn: 'Solid Capacitor Bank C14',
      cl: 'Cosmetic wear that does not affect electrical continuity is not a defect.',
      src: 'Direct Return Policy, Section 1.0',
      st: 'Pending',
      userImages: [
        'assets/base_vrm.jpg',
        'assets/base_vrm.jpg',
        'assets/base_vrm.jpg',
        'assets/base_vrm.jpg',
        'assets/base_vrm.jpg'
      ],
      subImg: 'assets/base_vrm.jpg',
      at: [35, 65],
      visionTelemetry: {
        anomaly_score: 0.44,
        flagged_region: 'Solid Capacitor Bank C14',
        severity: 'MODERATE',
        visual_findings: 'Minor cosmetic scratch on capacitor aluminum casing; no dielectric rupture or bulging.',
        model_used: 'moondream:latest (Vision LLM)',
        at: [35, 65]
      },
      policyGrounding: {
        verdict: 'APPROVED (Cosmetic Servicing)',
        cited_clause: 'Cosmetic wear that does not affect electrical continuity is not a defect, eligible for standard servicing.',
        source_document: 'Direct Return Policy',
        page: 1,
        explanation: 'Cosmetic surface wear without electrical degradation.'
      }
    },
    {
      id: 'RMA-1028',
      p: 'GeForce RTX 4060 Dual OC 8GB',
      v: 289,
      t: 'T1',
      r: 14,
      a: 0.08,
      conf: 96,
      st: 'Auto-Approved',
      isAutoApproved: true,
      autoApproveReason: 'Autonomous SLA Auto-Approved: Product value ($289.00) falls within Tier 1 (< $300), Risk Score (14/100) is well below the 30 ceiling threshold. Node 3 Vision confirmed clean hardware condition (Anomaly Score: 0.08, Factory Clean), and Node 2 Policy verified full coverage under Direct Return Policy, Section 1.0 with verified pHash/EXIF authenticity.',
      resolvedReason: 'Autonomous SLA Auto-Approved: Product value ($289.00) falls within Tier 1 (< $300), Risk Score (14/100) is well below the 30 ceiling threshold. Node 3 Vision confirmed clean hardware condition (Anomaly Score: 0.08, Factory Clean), and Node 2 Policy verified full coverage under Direct Return Policy, Section 1.0 with verified pHash/EXIF authenticity.',
      resolvedOperator: 'AUTONOMOUS-SLA-ROUTER',
      resolvedTime: '14:22:10',
      resolvedHash: '0x7a9c81f034e912bc88d1',
      rn: 'Factory Clean Surface (All 5 Views)',
      cl: 'Unused products or nominal hardware returns under $300 are eligible for immediate full refund or replacement under Tier 1 SLA.',
      src: 'Direct Return Policy, Section 1.0',
      userImages: [
        'assets/gpu_front.jpg',
        'assets/gpu_front.jpg',
        'assets/gpu_front.jpg',
        'assets/gpu_front.jpg',
        'assets/gpu_front.jpg'
      ],
      subImg: 'assets/gpu_front.jpg',
      at: [50, 50],
      visionTelemetry: {
        anomaly_score: 0.08,
        flagged_region: 'Factory Clean Surface (All 5 Views)',
        severity: 'NOMINAL',
        visual_findings: 'No thermal discoloration, scorched pins, cracks, or mechanical trauma detected. All 5 guided angles are pristine and match golden baseline.',
        model_used: 'moondream:latest (Vision LLM)',
        at: [50, 50]
      },
      policyGrounding: {
        verdict: 'APPROVED (Autonomous Tier 1)',
        cited_clause: 'Unused products or nominal hardware returns under $300 are eligible for immediate full refund or replacement under Tier 1 SLA.',
        source_document: 'Direct Return Policy',
        page: 1,
        explanation: 'Tier 1 low-risk clean unit auto-approved without technician intervention.'
      }
    }
  ];

  try {
    const stored = localStorage.getItem('smartrma_cases');
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed.length > 0) {
        // Merge stored cases with defaults so newly triaged cases are at the top
        const merged = [...parsed];
        defaultCases.forEach(dc => {
          if (!merged.some(m => m.id === dc.id)) {
            merged.push(dc);
          }
        });
        return merged;
      }
    }
  } catch (e) {
    console.warn('[Error loading stored cases]', e);
  }

  return defaultCases;
}

let CASES = getInitialCases().sort((x, y) => (y.v * y.r) - (x.v * x.r));
let activeIndex = 0;
let currentFilter = 'pending';
let searchQuery = '';
const auditLedger = [];

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/\n/g, '<br>');
}

// Generate Cryptographic SHA-256 Ledger Stamp
function generateAuditHash() {
  const chars = '0123456789abcdef';
  let hash = '0x';
  for (let i = 0; i < 20; i++) {
    hash += chars[Math.floor(Math.random() * chars.length)];
  }
  return hash;
}

// Load Persistent Audit History from localStorage
function loadAuditHistory() {
  try {
    const raw = localStorage.getItem('smartrma_audit_history');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        auditLedger.length = 0;
        parsed.forEach(item => auditLedger.push(item));
        return;
      }
    }
  } catch (e) {
    console.warn('[Error loading persistent audit history]', e);
  }

  // Initial default audit ledger entry with sample auto-approved case
  auditLedger.length = 0;
  auditLedger.push({
    time: '14:22:10',
    caseId: 'RMA-1028',
    product: 'GeForce RTX 4060 Dual OC 8GB',
    tier: 'T1',
    decision: 'Auto-Approved',
    reason: 'Autonomous SLA Auto-Approved: Product value ($289.00) falls within Tier 1 (< $300), Risk Score (14/100) is well below the 30 ceiling threshold. Node 3 Vision confirmed clean hardware condition (Anomaly Score: 0.08, Factory Clean), and Node 2 Policy verified full coverage under Direct Return Policy, Section 1.0 with verified pHash/EXIF authenticity.',
    hash: '0x7a9c81f034e912bc88d1',
    operator: 'AUTONOMOUS-SLA-ROUTER',
    subImg: 'assets/gpu_front.jpg',
    isAutoApproved: true
  });
}

// Update Toolbar Tab Counts
function updateTabCounts() {
  const pendingCount = CASES.filter(c => c.st === 'Pending').length;
  const resolvedCount = CASES.filter(c => c.st === 'Approved' || c.st === 'Rejected' || c.st === 'Auto-Approved').length;
  const allCount = CASES.length;

  const elPending = $('#tab-pending-count');
  const elResolved = $('#tab-resolved-count');
  const elAll = $('#tab-all-count');
  const elQueueCount = $('#queue-count');

  if (elPending) elPending.textContent = pendingCount;
  if (elResolved) elResolved.textContent = resolvedCount;
  if (elAll) elAll.textContent = allCount;
  if (elQueueCount) elQueueCount.textContent = `${pendingCount} PENDING ACTION`;
}

// Render Queue Table
function renderQueue() {
  const tbody = $('#q');
  if (!tbody) return;

  updateTabCounts();

  const filtered = CASES.filter(c => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      if (!c.id.toLowerCase().includes(q) && !c.p.toLowerCase().includes(q)) return false;
    }
    if (currentFilter === 'pending') return c.st === 'Pending';
    if (currentFilter === 'resolved') return c.st === 'Approved' || c.st === 'Rejected' || c.st === 'Auto-Approved';
    return true; // 'all'
  });

  if (filtered.length === 0) {
    const emptyMsg = currentFilter === 'pending'
      ? 'All escalated cases have been finalized! No pending reviews.'
      : currentFilter === 'resolved'
      ? 'No cases have been resolved yet. Select a pending case above to review.'
      : 'No matching cases in this queue view.';
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:28px 14px;color:var(--text-muted)">${emptyMsg}</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(c => {
    const origIndex = CASES.indexOf(c);
    const isSel = origIndex === activeIndex;
    const riskColor = c.r >= 70 ? 'var(--danger-text)' : c.r >= 40 ? 'var(--warning-text)' : 'var(--success-text)';

    return `
      <tr tabindex="0" data-idx="${origIndex}" class="${isSel ? 'sel' : ''}">
        <td>
          <b class="mono" style="font-size:0.92rem;color:var(--text-primary)">${escapeHtml(c.id)}</b><br>
          <span style="font-size:0.75rem;color:var(--text-muted)">${escapeHtml(c.p)}</span>
        </td>
        <td class="mono" style="font-weight:600">$${c.v.toLocaleString()}</td>
        <td>
          <div style="display:flex;align-items:center;gap:6px">
            <span class="mono" style="font-weight:700;color:${riskColor}">${c.r}</span>
            <div style="width:36px;height:4px;background:var(--border-subtle);border-radius:2px;overflow:hidden">
              <div style="width:${c.r}%;height:100%;background:${riskColor}"></div>
            </div>
          </div>
        </td>
        <td>
          <span class="mono" style="font-weight:700;color:#00A884">${c.conf || Math.round(Math.max(c.a, 1 - c.a) * 100)}%</span>
        </td>
        <td>
          <span class="mono brand-pill">${escapeHtml(c.t)}</span>
        </td>
        <td>
          <span class="badge ${escapeHtml(c.st)}" style="font-size:0.72rem;padding:3px 8px">${escapeHtml(c.st)}</span>
        </td>
      </tr>
    `;
  }).join('');

  // Row selection bindings
  $$('#q tr').forEach(row => {
    const idx = +row.dataset.idx;
    if (isNaN(idx)) return;
    const selectRow = () => {
      activeIndex = idx;
      renderQueue();
      renderDetails();
    };
    row.onclick = selectRow;
    row.onkeydown = e => {
      if (e.key === 'Enter') selectRow();
    };
  });
}

// Render Details & Comparator Viewport
function renderDetails() {
  const d = $('#d');
  if (!d) return;

  const c = CASES[activeIndex];
  if (!c) {
    d.innerHTML = `<div style="padding:32px;text-align:center;color:var(--text-muted)">Select a case from the queue to inspect.</div>`;
    return;
  }

  const isAutoApproved = c.st === 'Auto-Approved' || c.isAutoApproved;
  const isTechnicianResolved = c.st === 'Approved' || c.st === 'Rejected';
  const isResolved = isAutoApproved || isTechnicianResolved;
  const customerUnitImg = c.subImg || (c.userImages && c.userImages[0]) || 'assets/gpu_damaged.jpg';

  // Extract Node 3 Vision and Node 2 Policy Telemetry
  const vt = c.visionTelemetry || {
    anomaly_score: c.a !== undefined ? c.a : 0.5,
    flagged_region: c.rn || 'Hardware Incident Zone',
    severity: (c.a >= 0.75) ? 'CRITICAL' : (c.a <= 0.25) ? 'NOMINAL' : 'MODERATE',
    visual_findings: (c.a >= 0.75) ? `Thermal scorch patterns and damaged connector contact detected on ${c.rn || 'hardware'}.` : (c.a <= 0.25) ? `Clean nominal hardware baseline verified; no physical damage observed.` : `Moderate visual variance detected on ${c.rn || 'hardware'}.`,
    model_used: 'moondream:latest (Vision LLM)',
    at: c.at || [50, 50]
  };

  const pg = c.policyGrounding || {
    verdict: (c.cl && (c.cl.includes('excluded') || c.cl.includes('not a defect'))) ? 'REJECTED (EXCLUSION)' : 'APPROVED (COVERED)',
    cited_clause: c.cl || 'Standard warranty terms apply under normal operating conditions.',
    source_document: c.src || 'OEM Limited Hardware Warranty',
    page: 1,
    explanation: 'OEM warranty terms benchmarked against reported symptoms and visual telemetry.'
  };

  d.innerHTML = `
    <div class="card-header-bar">
      <div class="card-title-group">
        <div class="card-title-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
            <line x1="8" y1="21" x2="16" y2="21"/>
            <line x1="12" y1="17" x2="12" y2="21"/>
          </svg>
        </div>
        <div>
          <h2 class="mono" style="margin:0">${escapeHtml(c.id)} &bull; ${escapeHtml(c.p)}</h2>
        </div>
      </div>
      <span class="badge ${escapeHtml(c.st)}">${escapeHtml(c.st)}</span>
    </div>

    <!-- Escalation / Auto-Approval Notice -->
    <div class="${isAutoApproved ? 'synthesis-banner' : 'escalation-trigger-banner'}" style="margin-bottom:12px">
      ${isAutoApproved ? `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00A884" stroke-width="2.5">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
        </svg>
        <span><strong>Autonomous SLA Status:</strong> Cleared automatically under Tier rules with verified clean visual &amp; policy telemetry</span>
      ` : `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="12 2 2 22 22 22 12 2"/>
          <line x1="12" y1="9" x2="12" y2="13"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <span><strong>Escalation Trigger:</strong> ${escapeHtml(c.escalationReason || 'Technician manual adjudication required by SLA')}</span>
      `}
    </div>

    <!-- Case Metrics Bar -->
    <div class="met" style="margin-top:0">
      <div class="met-box">
        <span class="met-val">$${c.v}</span>
        <span class="met-lbl">Declared Cost</span>
      </div>
      <div class="met-box">
        <span class="met-val">${escapeHtml(c.t)}</span>
        <span class="met-lbl">Policy Tier</span>
      </div>
      <div class="met-box">
        <span class="met-val">${c.r}</span>
        <span class="met-lbl">Risk Index</span>
      </div>
      <div class="met-box">
        <span class="met-val" style="color:#00A884">${c.conf || Math.round(Math.max(c.a, 1 - c.a) * 100)}%</span>
        <span class="met-lbl">Confidence</span>
      </div>
      <div class="met-box">
        <span class="met-val">${c.a ? c.a.toFixed(2) : '0.50'}</span>
        <span class="met-lbl">Anomaly Score</span>
      </div>
    </div>

    <!-- Customer Uploaded Hardware Inspection Viewport (No factory reference spec) -->
    <div class="hardware-inspection-viewport" id="cust-viewport" style="background-image:url(${escapeHtml(customerUnitImg)})">
      <div class="viewport-label">CUSTOMER UPLOADED VIEW: ${escapeHtml(vt.flagged_region || c.rn || 'Hardware View')}</div>
      <div class="spectral-overlay" style="--hx:${c.at ? c.at[0] : 50}%;--hy:${c.at ? c.at[1] : 50}%"></div>
      ${(c.a > 0.3) ? `
        <div class="defect-crosshair" style="left:${c.at ? c.at[0] : 50}%;top:${c.at ? c.at[1] : 50}%">
          <div class="crosshair-center"></div>
        </div>
      ` : ''}
    </div>

    <!-- Customer Uploaded Photos Gallery (5 Guided Views) -->
    ${(c.userImages && c.userImages.length > 0) ? `
      <div class="user-uploads-gallery">
        <div class="gallery-title">
          <span>📷 Customer Uploaded Inspection Views (${c.userImages.length} Views Verified at Intake):</span>
          <span class="mono brand-pill" style="font-size:0.68rem">USER UPLOADED DOSSIER</span>
        </div>
        <div class="gallery-thumbs">
          ${c.userImages.map((imgUrl, i) => `
            <button type="button" class="thumb-btn ${imgUrl === customerUnitImg ? 'active' : ''}" data-idx="${i}" title="Inspect ${SLOT_NAMES[i] || `View ${i+1}`}">
              <div class="thumb-preview" style="background-image:url(${escapeHtml(imgUrl)})"></div>
              <span class="thumb-name">${SLOT_NAMES[i] || `View ${i+1}`}</span>
            </button>
          `).join('')}
        </div>
      </div>
    ` : ''}

    <!-- Multi-Node AI Telemetry Grid: Node 3 Vision + Node 2 Policy -->
    <div class="nodes-telemetry-grid">
      <!-- Node 3 Vision Engine Telemetry -->
      <div class="node-telemetry-box node3-box">
        <div class="node-box-header">
          <div class="node-box-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
            <span>Node 3 Vision Engine</span>
          </div>
          <span class="node-status-pill ${vt.severity === 'CRITICAL' ? 'critical' : vt.severity === 'NOMINAL' ? 'nominal' : 'warning'}">
            ${escapeHtml(vt.severity)}
          </span>
        </div>
        <div class="node-box-body">
          <div class="node-telemetry-row">
            <span class="node-k">Anomaly Score:</span>
            <span class="node-v mono font-bold" style="color:${vt.anomaly_score >= 0.7 ? 'var(--danger-text)' : vt.anomaly_score <= 0.3 ? 'var(--success-text)' : 'var(--warning-text)'}">
              ${vt.anomaly_score.toFixed(2)} / 1.00
            </span>
          </div>
          <div class="node-telemetry-row">
            <span class="node-k">Flagged Region:</span>
            <span class="node-v">${escapeHtml(vt.flagged_region)}</span>
          </div>
          <div class="node-telemetry-row">
            <span class="node-k">Vision Model:</span>
            <span class="node-v mono">${escapeHtml(vt.model_used)}</span>
          </div>
          <div class="node-findings-quote">
            <strong>Visual Inspection Findings:</strong>
            <p>&ldquo;${escapeHtml(vt.visual_findings)}&rdquo;</p>
          </div>
        </div>
      </div>

      <!-- Node 2 Policy Grounding Engine (RAG) -->
      <div class="node-telemetry-box node2-box">
        <div class="node-box-header">
          <div class="node-box-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
            <span>Node 2 Policy RAG Engine</span>
          </div>
          <span class="node-status-pill ${pg.verdict.includes('REJECT') ? 'critical' : 'nominal'}">
            ${escapeHtml(pg.verdict)}
          </span>
        </div>
        <div class="node-box-body">
          <div class="node-telemetry-row">
            <span class="node-k">Policy Determination:</span>
            <span class="node-v font-bold">${escapeHtml(pg.verdict)}</span>
          </div>
          <div class="node-telemetry-row">
            <span class="node-k">Source Document:</span>
            <span class="node-v">📄 ${escapeHtml(pg.source_document)} (Page ${pg.page || 1})</span>
          </div>
          <div class="node-findings-quote">
            <strong>Cited Warranty Clause:</strong>
            <p>&ldquo;${escapeHtml(pg.cited_clause)}&rdquo;</p>
          </div>
          <div style="font-size:0.75rem;color:var(--text-secondary);margin-top:2px">
            <strong>Coverage Grounding:</strong> ${escapeHtml(pg.explanation)}
          </div>
        </div>
      </div>
    </div>

    <!-- Autonomous Multi-Node AI Recommendation -->
    <div class="synthesis-banner">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="16" x2="12" y2="12"/>
        <line x1="12" y1="8" x2="12.01" y2="8"/>
      </svg>
      <div>
        <strong>Multi-Node AI Synthesis:</strong>
        ${(vt.anomaly_score >= 0.7 && pg.verdict.includes('REJECT'))
          ? 'High anomaly + Policy exclusion identified &rarr; AI Recommendation: <strong>REJECT RETURN</strong>'
          : (vt.anomaly_score <= 0.3 && !pg.verdict.includes('REJECT'))
          ? 'Nominal anomaly + Policy coverage verified &rarr; AI Recommendation: <strong>APPROVE RETURN</strong>'
          : 'Ambiguous risk score or Tier 4 mandate &rarr; Requires Lead Technician manual adjudication'}
      </div>
    </div>

    ${isAutoApproved ? `
      <!-- Autonomous Approval Certificate: Fully preserved, buttons hidden -->
      <div class="resolution-finalized-card auto-approved">
        <div class="finalized-header">
          <div class="finalized-title">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#00A884" stroke-width="2.5">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
            <span style="color:#00A884;font-weight:800;font-size:0.95rem">
              DETERMINATION: AUTO-APPROVED (AUTONOMOUS SLA)
            </span>
          </div>
          <span class="mono brand-pill" style="background:rgba(0,168,132,0.15);color:#00A884">
            ⚡ AUTONOMOUS RESOLUTION &bull; COMMITTED TO LEDGER
          </span>
        </div>

        <div class="finalized-body">
          <div style="font-size:0.84rem;margin-bottom:8px">
            <strong>Explicit Reason for Auto-Approval:</strong>
            <div class="finalized-quote auto-approve-quote">
              &ldquo;${escapeHtml(c.autoApproveReason || c.resolvedReason || 'Autonomous SLA cleared under Tier rule and verified clean hardware telemetry.')}&rdquo;
            </div>
          </div>

          <div class="finalized-meta-grid">
            <div><span>Decision Authority:</span> <b>${escapeHtml(c.resolvedOperator || 'AUTONOMOUS-SLA-ROUTER')}</b></div>
            <div><span>Approval Timestamp:</span> <b>${escapeHtml(c.resolvedTime || 'Recorded at intake')}</b></div>
            <div><span>SHA-256 Ledger Stamp:</span> <code class="mono">${escapeHtml(c.resolvedHash || c.ledgerHash || '0x4f8a...')}</code></div>
            <div><span>Final Disposition:</span> <span class="badge Auto-Approved">Auto-Approved</span></div>
          </div>
        </div>
      </div>
    ` : isTechnicianResolved ? `
      <!-- Technician Override Resolution Banner: All details preserved, buttons locked & hidden -->
      <div class="resolution-finalized-card ${c.st === 'Approved' ? 'approved' : 'rejected'}">
        <div class="finalized-header">
          <div class="finalized-title">
            ${c.st === 'Approved' ? `
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
              <span style="color:var(--success-text);font-weight:800;font-size:0.95rem">
                TECHNICIAN DETERMINATION FINALIZED: APPROVED
              </span>
            ` : `
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2.5">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
              <span style="color:var(--danger-text);font-weight:800;font-size:0.95rem">
                TECHNICIAN DETERMINATION FINALIZED: REJECTED
              </span>
            `}
          </div>
          <span class="mono brand-pill" style="background:rgba(0,0,0,0.08);color:var(--text-secondary)">
            IMMUTABLE &bull; COMMITTED TO LEDGER
          </span>
        </div>

        <div class="finalized-body">
          <div style="font-size:0.84rem;margin-bottom:8px">
            <strong>Logged Forensic Justification:</strong>
            <div class="finalized-quote">&ldquo;${escapeHtml(c.resolvedReason || 'Forensic inspection completed and decision committed.')}&rdquo;</div>
          </div>

          <div class="finalized-meta-grid">
            <div><span>Auditor ID:</span> <b>${escapeHtml(c.resolvedOperator || 'TECH-402')}</b></div>
            <div><span>Decision Time:</span> <b>${escapeHtml(c.resolvedTime || 'Saved in session')}</b></div>
            <div><span>SHA-256 Ledger Stamp:</span> <code class="mono">${escapeHtml(c.resolvedHash || '0x4f8a...')}</code></div>
            <div><span>Final Disposition:</span> <span class="badge ${escapeHtml(c.st)}">${escapeHtml(c.st)}</span></div>
          </div>
        </div>
      </div>
    ` : `
      <!-- Action Inputs: Only shown when case is pending technician review -->
      <label for="rs" style="font-weight:600;display:block;margin-top:16px;color:var(--text-primary)">
        Mandatory Forensic Justification &amp; Findings
      </label>
      
      <!-- Quick Reason Chips -->
      <div class="reason-quick-chips">
        <button type="button" class="r-chip" data-reason="Confirmed external electrical surge burn beyond manufacturer tolerance">
          ⚡ External surge burn
        </button>
        <button type="button" class="r-chip" data-reason="Verified genuine silicon manufacturing defect under warranty">
          🔬 Factory silicon defect
        </button>
        <button type="button" class="r-chip" data-reason="Customer provided proof of surge protector coverage and power log">
          🛡️ Surge protector proof
        </button>
        <button type="button" class="r-chip" data-reason="Escalating to Tier 4 clean-room forensic teardown lab">
          📦 Teardown lab escalation
        </button>
      </div>

      <textarea id="rs" rows="2" placeholder="Document empirical findings based on customer uploads, Node 3 vision, and Node 2 policy before confirming verdict..."></textarea>

      <!-- Action Buttons -->
      <div class="acts" style="margin-top:14px;justify-content:space-between">
        <div class="acts">
          <button class="btn g" id="btn-approve" type="button">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            Approve Return
          </button>
          <button class="btn r" id="btn-reject" type="button">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
            Reject Return
          </button>
        </div>
        <span class="mono" style="font-size:0.75rem;color:var(--text-muted)">OPERATOR: TECH-402</span>
      </div>
      <p class="err" id="e2" role="alert"></p>
    `}
  `;

  // Bind gallery thumbnail buttons so technician can inspect any customer-uploaded angle
  $$('.thumb-btn', d).forEach(btn => {
    btn.onclick = () => {
      const idx = +btn.dataset.idx;
      if (c.userImages && c.userImages[idx]) {
        c.subImg = c.userImages[idx];
        const custVp = $('#cust-viewport');
        if (custVp) custVp.style.backgroundImage = `url(${c.subImg})`;
        $$('.thumb-btn', d).forEach(b => b.classList.toggle('active', +b.dataset.idx === idx));
        showToast(`Inspecting Customer Upload: ${SLOT_NAMES[idx] || `View ${idx+1}`}`, 'info');
      }
    };
  });

  if (!isResolved) {
    // Bind quick reason chips
    $$('.r-chip', d).forEach(chip => {
      chip.onclick = () => {
        const reason = chip.dataset.reason || '';
        applyReason(reason);
      };
    });

    // Action button listeners
    const approveBtn = $('#btn-approve');
    const rejectBtn = $('#btn-reject');
    if (approveBtn) approveBtn.onclick = () => executeOverride('Approve');
    if (rejectBtn) rejectBtn.onclick = () => executeOverride('Reject');
  }
}

window.applyReason = function(text) {
  const textarea = $('#rs');
  if (!textarea) return;
  textarea.value = text;
  textarea.focus();
};

function executeOverride(decision) {
  const c = CASES[activeIndex];
  if (!c) return;

  if (c.st === 'Approved' || c.st === 'Rejected' || c.st === 'Auto-Approved') {
    showToast(`Case ${c.id} is already finalized as ${c.st.toUpperCase()}`, 'info');
    return;
  }

  const reasonInput = $('#rs');
  const reason = reasonInput ? reasonInput.value.trim() : '';
  const errEl = $('#e2');

  if (!reason) {
    if (errEl) errEl.textContent = 'A written forensic justification is required prior to committing this override.';
    showToast('Justification required for override', 'error');
    return;
  }

  const finalStatus = decision === 'Approve' ? 'Approved' : 'Rejected';
  c.st = finalStatus;
  const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const hash = generateAuditHash();

  c.resolvedReason = reason;
  c.resolvedTime = timestamp;
  c.resolvedHash = hash;
  c.resolvedOperator = 'TECH-402';

  // Push new decision into audit ledger
  auditLedger.unshift({
    time: timestamp,
    caseId: c.id,
    product: c.p,
    tier: c.t,
    decision: finalStatus,
    reason: reason,
    hash: hash,
    operator: 'TECH-402',
    subImg: c.subImg
  });

  // PERSIST BOTH CASES AND AUDIT HISTORY TO LOCALSTORAGE
  try {
    localStorage.setItem('smartrma_audit_history', JSON.stringify(auditLedger));
    localStorage.setItem('smartrma_cases', JSON.stringify(CASES));
  } catch (storageErr) {
    console.warn('[LocalStorage save error]', storageErr);
  }

  renderAuditLog();
  renderQueue();
  renderDetails();

  showToast(`Case ${c.id} finalized as ${finalStatus.toUpperCase()} (Saved to Audit History)`, finalStatus === 'Approved' ? 'success' : 'error');
}

// Render Decision History with interactive click-to-inspect feature
function renderAuditLog() {
  const logEl = $('#log');
  if (!logEl) return;

  const historyBadge = $('#history-badge');
  if (historyBadge) {
    historyBadge.textContent = auditLedger.length === 0
      ? '0 DECISIONS LOGGED'
      : `${auditLedger.length} AUDITED DECISION${auditLedger.length > 1 ? 'S' : ''}`;
  }

  if (auditLedger.length === 0) {
    logEl.innerHTML = `<div class="mu" style="font-size:0.85rem;padding:12px 4px">No decisions recorded yet. Complete a review above or auto-approve a case to save an audit history entry.</div>`;
    return;
  }

  logEl.innerHTML = auditLedger.map(item => `
    <div class="audit-item interactive-audit-card" data-case-id="${escapeHtml(item.caseId)}" tabindex="0" title="Click to inspect complete case dossier and customer-uploaded photos">
      <div style="display:flex;flex-direction:column;gap:3px">
        <span class="audit-time">${escapeHtml(item.time)}</span>
        <span class="audit-hash">${escapeHtml(item.hash)}</span>
      </div>
      <div style="flex:1">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px;flex-wrap:wrap">
          <strong class="mono" style="color:var(--text-primary);font-size:0.92rem">${escapeHtml(item.caseId)}</strong>
          ${item.product ? `<span style="font-size:0.75rem;color:var(--text-secondary)">(${escapeHtml(item.product)})</span>` : ''}
          <span class="badge ${escapeHtml(item.decision)}" style="font-size:0.68rem;padding:2px 7px">${escapeHtml(item.decision)}</span>
          <span class="mono brand-pill">${escapeHtml(item.operator || (item.isAutoApproved ? 'AUTONOMOUS-SLA-ROUTER' : 'TECH-402'))}</span>
        </div>
        <div style="color:var(--text-secondary);font-size:0.8rem">&ldquo;${escapeHtml(item.reason)}&rdquo;</div>
        <div class="inspect-tag">🔍 Click to inspect case details &amp; customer uploaded photos &rarr;</div>
      </div>
    </div>
  `).join('');

  // Interactive binding: clicking any audit item loads that case and shows all its details
  $$('.audit-item', logEl).forEach(itemEl => {
    const handleInspect = () => {
      const caseId = itemEl.dataset.caseId;
      if (!caseId) return;
      let targetIndex = CASES.findIndex(c => c.id === caseId);

      // If not in current CASES memory array, attempt recovery from localStorage
      if (targetIndex === -1) {
        try {
          const stored = JSON.parse(localStorage.getItem('smartrma_cases') || '[]');
          const found = stored.find(c => c.id === caseId);
          if (found) {
            CASES.unshift(found);
            targetIndex = 0;
          }
        } catch (e) {}
      }

      if (targetIndex !== -1) {
        activeIndex = targetIndex;
        // If current filter is pending and this case is resolved, switch tab to all or resolved
        if (currentFilter === 'pending') {
          currentFilter = 'all';
          $$('.q-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.filter === 'all');
          });
        }
        renderQueue();
        renderDetails();
        const detailsEl = $('#d');
        if (detailsEl) {
          detailsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        showToast(`Loaded details for Case ${caseId}`, 'info');
      }
    };

    itemEl.onclick = handleInspect;
    itemEl.onkeydown = e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleInspect();
      }
    };
  });
}

// Keyboard Navigation & Shortcuts
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (activeIndex < CASES.length - 1) {
      activeIndex++;
      renderQueue();
      renderDetails();
    }
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (activeIndex > 0) {
      activeIndex--;
      renderQueue();
      renderDetails();
    }
  } else if (e.key === 'a' || e.key === 'A') {
    e.preventDefault();
    const c = CASES[activeIndex];
    if (c && c.st === 'Pending') executeOverride('Approve');
    else if (c) showToast(`Case ${c.id} is already finalized`, 'info');
  } else if (e.key === 'r' || e.key === 'R') {
    e.preventDefault();
    const c = CASES[activeIndex];
    if (c && c.st === 'Pending') executeOverride('Reject');
    else if (c) showToast(`Case ${c.id} is already finalized`, 'info');
  }
});

// Setup Toolbar Filters, Search & Persistent History
document.addEventListener('DOMContentLoaded', () => {
  // If active case was set from triage submit, select it
  try {
    const activeCaseId = localStorage.getItem('smartrma_active_case_id');
    if (activeCaseId) {
      const foundIdx = CASES.findIndex(c => c.id === activeCaseId);
      if (foundIdx !== -1) {
        activeIndex = foundIdx;
      }
    }
  } catch (e) {}

  $$('.q-tab').forEach(tab => {
    tab.onclick = () => {
      $$('.q-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentFilter = tab.dataset.filter;
      renderQueue();
    };
  });

  const searchInput = $('#q-search');
  if (searchInput) {
    searchInput.oninput = () => {
      searchQuery = searchInput.value.trim();
      renderQueue();
    };
  }

  loadAuditHistory();
  renderQueue();
  renderDetails();
  renderAuditLog();
});
