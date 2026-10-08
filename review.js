// SmartRMA Technician Review & Hardware Comparator Workbench

const CASES = [
  {
    id: 'RMA-1042',
    p: 'RTX 4090 OC Founders Edition',
    v: 1240,
    t: 'T3',
    r: 80,
    a: 0.86,
    conf: 94,
    rn: '12VHPWR Power Connector (Pin 3)',
    cl: 'Damage from electrical overload or scorched pin connectors is explicitly excluded.',
    st: 'Pending',
    refImg: 'assets/rma_055_power_12vhpwr_socket_ortho_90_vis_clean.jpg',
    subImg: 'assets/rma_056_power_12vhpwr_socket_ortho_90_vis_defect.jpg',
    at: [62, 38]
  },
  {
    id: 'RMA-1045',
    p: 'NVIDIA RTX 6000 Ada Server Edition',
    v: 3150,
    t: 'T4',
    r: 55,
    a: 0.62,
    conf: 84,
    rn: 'GPU Core BGA / Power Stages',
    cl: 'High-value enterprise returns require mandatory physical teardown inspection prior to credit release.',
    st: 'Pending',
    refImg: 'assets/rma_001_gpu_silicon_core_ortho_90_vis_clean.jpg',
    subImg: 'assets/rma_003_gpu_silicon_core_ortho_90_thermal_flir.jpg',
    at: [48, 52]
  },
  {
    id: 'RMA-1039',
    p: 'RTX 4070 Ti Super 16GB',
    v: 690,
    t: 'T2',
    r: 41,
    a: 0.58,
    conf: 84,
    rn: 'VRAM Bank A0-A2 Traces',
    cl: 'Defects in silicon materials or factory soldering under normal use are fully covered.',
    st: 'Pending',
    refImg: 'assets/rma_019_gddr6x_vram_bank_a_ortho_90_vis_clean.jpg',
    subImg: 'assets/rma_020_gddr6x_vram_bank_a_ortho_90_vis_defect.jpg',
    at: [48, 52]
  },
  {
    id: 'RMA-1036',
    p: 'Mini-ITX Motherboard Z790-I',
    v: 260,
    t: 'T1',
    r: 34,
    a: 0.44,
    conf: 84,
    rn: 'Solid Capacitor Bank C14',
    cl: 'Cosmetic wear that does not affect electrical continuity is not a defect.',
    st: 'Pending',
    refImg: 'assets/base_vrm.jpg',
    subImg: 'assets/rma_018_gpu_silicon_core_grazing_high_specular_laser_contour.jpg',
    at: [35, 65]
  },
  {
    id: 'RMA-1033',
    p: 'RTX 4060 Dual OC 8GB',
    v: 980,
    t: 'T2',
    r: 8,
    a: 0.12,
    conf: 94,
    rn: 'No Region Flagged (Clean Spec)',
    cl: 'Unused products in original condition may be returned within the standard 30-day window.',
    st: 'Pending',
    refImg: 'assets/rma_089_pcie4_gold_fingers_ortho_90_vis_clean.jpg',
    subImg: 'assets/rma_089_pcie4_gold_fingers_ortho_90_vis_clean.jpg',
    at: [30, 70]
  }
].sort((x, y) => (y.v * y.r) - (x.v * x.r));

let activeIndex = 0;
let currentFilter = 'all';
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

// Generate Simulated SHA-256 Ledger Stamp
function generateAuditHash() {
  const chars = '0123456789abcdef';
  let hash = '0x';
  for (let i = 0; i < 16; i++) {
    hash += chars[Math.floor(Math.random() * chars.length)];
  }
  return hash;
}

// Render Queue Table
function renderQueue() {
  const tbody = $('#q');
  if (!tbody) return;

  const filtered = CASES.filter((c, idx) => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      if (!c.id.toLowerCase().includes(q) && !c.p.toLowerCase().includes(q)) return false;
    }
    if (currentFilter === 'high-risk') return c.r >= 50;
    if (currentFilter === 't3-t4') return c.t === 'T3' || c.t === 'T4';
    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted)">No matching cases in this queue view.</td></tr>`;
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
  if (!c) return;

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
        <span class="met-val">${c.a.toFixed(2)}</span>
        <span class="met-lbl">Anomaly Score</span>
      </div>
    </div>

    <!-- Dual Comparator Viewports -->
    <div class="comparator-grid">
      <div class="img" style="background-image:url(${escapeHtml(c.refImg)})">
        <div class="viewport-label">GOLDEN REFERENCE SAMPLE</div>
      </div>
      <div class="img" style="background-image:url(${escapeHtml(c.subImg)})">
        <div class="viewport-label">CUSTOMER UNIT: ${escapeHtml(c.rn)}</div>
        <div class="spectral-overlay" style="--hx:${c.at[0]}%;--hy:${c.at[1]}%"></div>
        ${c.a > 0.3 ? `
          <div class="defect-crosshair" style="left:${c.at[0]}%;top:${c.at[1]}%">
            <div class="crosshair-center"></div>
          </div>
        ` : ''}
      </div>
    </div>

    <!-- Policy Excerpt -->
    <div class="warranty-clause-card" style="margin:12px 0">
      <div class="clause-badge">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        Flagged Region: ${escapeHtml(c.rn)}
      </div>
      <div class="clause-text">&ldquo;${escapeHtml(c.cl)}&rdquo;</div>
    </div>

    <!-- Override Reason Section -->
    <label for="rs" style="font-weight:600;display:block;margin-top:16px;color:var(--text-primary)">
      Mandatory Override Justification &amp; Findings
    </label>
    
    <!-- Quick Reason Chips -->
    <div class="reason-quick-chips">
      <button type="button" class="r-chip" data-reason="Confirmed external electrical surge burn">
        ⚡ External surge burn
      </button>
      <button type="button" class="r-chip" data-reason="Verified genuine silicon manufacturing defect">
        🔬 Verified factory defect
      </button>
      <button type="button" class="r-chip" data-reason="Customer provided proof of surge protector coverage">
        🛡️ Surge protector proof
      </button>
      <button type="button" class="r-chip" data-reason="Escalating to Tier 4 Forensic teardown lab">
        📦 Forensic lab escalation
      </button>
    </div>

    <textarea id="rs" rows="2" placeholder="Document empirical findings before confirming or overriding triage verdict..."></textarea>

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
  `;

  // Bind quick reason chips safely
  $$('.r-chip', d).forEach(chip => {
    chip.onclick = () => {
      const reason = chip.dataset.reason || '';
      applyReason(reason);
    };
  });

  // Action listeners
  const approveBtn = $('#btn-approve');
  const rejectBtn = $('#btn-reject');
  if (approveBtn) approveBtn.onclick = () => executeOverride('Approve');
  if (rejectBtn) rejectBtn.onclick = () => executeOverride('Reject');
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

  const reasonInput = $('#rs');
  const reason = reasonInput ? reasonInput.value.trim() : '';
  const errEl = $('#e2');

  if (!reason) {
    if (errEl) errEl.textContent = 'A written forensic justification is required prior to committing this override.';
    showToast('Justification required for override', 'error');
    return;
  }

  c.st = decision;
  const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const hash = generateAuditHash();

  auditLedger.unshift({
    time: timestamp,
    caseId: c.id,
    decision,
    reason,
    hash,
    operator: 'TECH-402'
  });

  renderAuditLog();
  renderQueue();
  renderDetails();

  showToast(`Case ${c.id} updated to ${decision.toUpperCase()}`, decision === 'Approve' ? 'success' : 'error');
}

function renderAuditLog() {
  const logEl = $('#log');
  if (!logEl) return;

  if (auditLedger.length === 0) {
    logEl.innerHTML = `<div class="mu" style="font-size:0.85rem">No technician overrides recorded in this active session.</div>`;
    return;
  }

  logEl.innerHTML = auditLedger.map(item => `
    <div class="audit-item">
      <div style="display:flex;flex-direction:column;gap:2px">
        <span class="audit-time">${escapeHtml(item.time)}</span>
        <span class="audit-hash">${escapeHtml(item.hash)}</span>
      </div>
      <div style="flex:1">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
          <strong class="mono" style="color:var(--text-primary)">${escapeHtml(item.caseId)}</strong>
          <span class="badge ${escapeHtml(item.decision)}" style="font-size:0.68rem;padding:2px 7px">${escapeHtml(item.decision)}</span>
          <span class="mono brand-pill">${escapeHtml(item.operator)}</span>
        </div>
        <div style="color:var(--text-secondary);font-size:0.8rem">${escapeHtml(item.reason)}</div>
      </div>
    </div>
  `).join('');
}

// Keyboard Navigation & Shortcuts
document.addEventListener('keydown', e => {
  // Ignore shortcuts if user is typing in textarea or search input
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
    executeOverride('Approve');
  } else if (e.key === 'r' || e.key === 'R') {
    e.preventDefault();
    executeOverride('Reject');
  }
});

// Setup Toolbar Filters & Search
document.addEventListener('DOMContentLoaded', () => {
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

  renderQueue();
  renderDetails();
});
