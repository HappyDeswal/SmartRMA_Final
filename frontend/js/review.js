// Server-owned cases and append-only decision history. No fabricated browser records.
let CASES = [];
let auditLedger = [];
let activeCaseId = null;
let currentFilter = 'pending';
let currentAuditFilter = 'all';
let searchQuery = '';
let saving = false;
let historicalCase = null;
let historicalBlockHash = null;
const SLOT_NAMES = ['Full Product Front','Full Product Back','Contacts & Connectors','Damage or Detail View','Serial Barcode Label'];
function isPendingTechnicianReview(c) { return c.st === 'Pending' && !c.resolvedOperator; }
function filteredCases() {
  return CASES.filter(c => {
    const match = [c.id,c.orderId,c.serialNumber,c.p,c.st].some(value=>String(value||'').toLowerCase().includes(searchQuery));
    return match && (currentFilter==='all' || currentFilter==='pending' && isPendingTechnicianReview(c) ||
      currentFilter==='approved' && ['Approved','Auto-Approved'].includes(c.st) ||
      currentFilter==='rejected' && c.st==='Rejected' || currentFilter==='resolved' && Boolean(c.resolvedOperator));
  });
}
function count(id,value) { const el=$('#'+id); if (el) el.textContent=value; }
function updateWorkbenchVisibility() {
  const populated=CASES.length>0 || auditLedger.length>0;
  $('#empty-workbench').style.display=populated?'none':'flex';
  $('#workbench-grid').style.display=CASES.length?'grid':'none';
  $('#audit-ledger-card').style.display=populated?'block':'none';
  $('#btn-purge-audits').style.display=populated?'inline-flex':'none';
}
function renderQueue() {
  count('tab-pending-count',CASES.filter(isPendingTechnicianReview).length);
  count('tab-approved-count',CASES.filter(c=>['Approved','Auto-Approved'].includes(c.st)).length);
  count('tab-rejected-count',CASES.filter(c=>c.st==='Rejected').length);
  count('tab-resolved-count',CASES.filter(c=>c.resolvedOperator).length);
  count('tab-all-count',CASES.length);
  count('queue-count',`${CASES.filter(isPendingTechnicianReview).length} PENDING REVIEW`);
  const rows=filteredCases();
  if (!rows.some(c=>c.id===activeCaseId)) activeCaseId=rows[0]?.id || null;
  $('#q').innerHTML=rows.length ? rows.map(c=>`<tr tabindex="0" data-id="${escapeHtml(c.id)}" class="${c.id===activeCaseId?'sel':''}">
    <td><b>${escapeHtml(c.id)}</b><br>${escapeHtml(c.p)}</td><td>$${Number(c.v).toLocaleString()}</td>
    <td>${c.r==null?'Unassessed':Number(c.r)}</td><td>${Number(c.conf)}%</td><td>${escapeHtml(c.t)}</td>
    <td>${escapeHtml(c.st)}${isPendingTechnicianReview(c)?' (pending review)':''}</td></tr>`).join('') :
    '<tr><td colspan="6">No cases match this filter.</td></tr>';
  $$('#q tr[data-id]').forEach(row=>{
    const select=()=>{historicalCase=null;activeCaseId=row.dataset.id;renderQueue();renderDetails();};
    row.onclick=select;row.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();select();}};
  });
  updateWorkbenchVisibility();
}
function renderDetails() {
  const c=historicalCase || CASES.find(row=>row.id===activeCaseId);
  if (!c) { $('#d').innerHTML='<p>No case selected.</p>'; return; }
  const vt=c.visionTelemetry || {};
  const pg=c.policyGrounding || {};
  const serial=vt.serial_verification || {status:'UNVERIFIED',details:'No independent serial observation recorded.'};
  const model=vt.model_verification || {status:'UNVERIFIED',details:'No independent model observation recorded.'};
  const legacy= !Object.hasOwn(vt,'assessment_available');
  const images=(c.imageSlots || (c.userImages || []).map((src,i)=>({src,slot:i,name:SLOT_NAMES[i]}))).filter(i=>imageSource(i.src));
  const selected=images.find(i=>i.slot===c.selectedSlot) || images[0];
  c.selectedSlot=selected?.slot;
  // Model coordinates are optional estimates. Never display a simulated heatmap.
  const coordinates=vt.defect_coordinates;
  const showMarker=coordinates && selected?.slot===vt.flagged_slot;
  const resolved=Boolean(c.resolvedOperator);
  const automatic=c.decisionMode==='IMAGE_RULES_V2' && c.st!=='Pending' && !c.resolvedOperator;
  const tampered=c._integrity==='TAMPERED';
  $('#d').innerHTML=`<div class="card-header-bar"><h2>${escapeHtml(c.id)}</h2><span class="badge">${escapeHtml(c.st)}</span></div>
    ${tampered?'<p class="err">Dossier integrity failed. Decisions and exports are blocked until the verified record is restored.</p>':''}
    ${legacy?'<p class="err">Legacy record: measurements and identity checks predate the local-only validation changes. Re-inspect before relying on them.</p>':''}
    <p><strong>${escapeHtml(c.p)}</strong><br>Order: ${escapeHtml(c.orderId)} • Serial: ${escapeHtml(c.serialNumber)}</p>
    <div class="met"><div class="met-box"><span class="met-val">$${Number(c.v).toLocaleString()}</span><span class="met-lbl">Value</span></div>
      <div class="met-box"><span class="met-val">${escapeHtml(c.t)}</span><span class="met-lbl">Tier</span></div>
      <div class="met-box"><span class="met-val">${c.r==null?'Unassessed':Number(c.r)}</span><span class="met-lbl">Risk estimate</span></div>
      <div class="met-box"><span class="met-val">${Number(c.conf)}%</span><span class="met-lbl">Model confidence estimate</span></div></div>
    <p style="white-space:pre-wrap">${escapeHtml(c.symptom)}</p>
    <div class="identity-badges-grid"><div class="identity-badge-box"><b>Serial: ${escapeHtml(legacy?'UNVERIFIED (legacy)':serial.status)}</b>
      <p>Observed: ${escapeHtml(serial.detected_serial || 'Unreadable / not visible')}</p><p>${escapeHtml(serial.details)}</p></div>
      <div class="identity-badge-box"><b>Model: ${escapeHtml(legacy?'UNVERIFIED (legacy)':model.status)}</b><p>${escapeHtml(model.detected_model || 'Not verified')}</p></div></div>
    ${selected?`<div class="hardware-inspection-viewport"><img id="cust-viewport-img" class="viewport-main-img" src="${escapeHtml(imageSource(selected.src))}" alt="${escapeHtml(selected.name || SLOT_NAMES[selected.slot])}">
      <div class="viewport-label">${escapeHtml(selected.name || SLOT_NAMES[selected.slot])}${showMarker?' • Model-estimated location':''}</div>
      ${showMarker?`<div class="defect-crosshair" style="left:${Number(coordinates.center_x_pct)}%;top:${Number(coordinates.center_y_pct)}%"><div class="crosshair-center"></div></div>`:''}</div>`:'<p>No valid photo recorded.</p>'}
    <div class="gallery-thumbs">${images.map(image=>`<button type="button" class="thumb-btn ${selected?.slot===image.slot?'active':''}" data-slot="${image.slot}">
      <img class="thumb-img" src="${escapeHtml(imageSource(image.src))}" alt="${escapeHtml(image.name || SLOT_NAMES[image.slot])}">
      <span>${escapeHtml(image.name || SLOT_NAMES[image.slot])}</span></button>`).join('')}</div>
    <div class="nodes-telemetry-grid"><div class="node-telemetry-box"><h3>Local vision findings</h3>
      <p>Model: ${escapeHtml(vt.model_used || 'Unavailable')}</p><p style="white-space:pre-wrap">${escapeHtml(vt.visual_findings || 'No inspection completed.')}</p>
      <p>Confidence and coordinates are model estimates, not calibrated measurements.</p>
      ${(vt.hardware_recognition || []).map(h=>`<p><b>Local hardware recognition (${escapeHtml(h.name)}):</b> ${escapeHtml(String(h.product_type).replaceAll('_',' '))} · ${Number.isFinite(h.score)?(h.score*100).toFixed(1)+'%':'Unavailable'} recognition score. Advisory only; this does not measure damage or determine the return decision.</p>`).join('')}
      ${(vt.inspection_points || []).map(point=>`<p><b>${escapeHtml(point.point)}: ${escapeHtml(point.status)}</b><br>${escapeHtml(point.details)}</p>`).join('')}</div>
      <div class="node-telemetry-box"><h3>Policy suggestion: ${escapeHtml(pg.verdict || 'Unassessed')}</h3>
      <p>${escapeHtml(pg.source_document || 'No indexed source')}${pg.page?` — page ${Number(pg.page)}`:''}</p>
      <blockquote>${escapeHtml(pg.cited_clause || 'No applicable clause recorded.')}</blockquote><p>${escapeHtml(pg.explanation)}</p></div></div>
    ${historicalCase?`<div class="resolution-finalized-card"><b>Verified historical event — read-only</b><p>Recorded status: ${escapeHtml(c.st)}</p><p>${escapeHtml(c.resolvedReason || c.escalationReason)}</p><code>${escapeHtml(historicalBlockHash)}</code><button id="btn-current-case" type="button" class="btn">Open current case</button></div>`:tampered?'<p class="err">Open a verified audit event below to inspect the original dossier.</p>':automatic&&!c.reopened?`<div class="resolution-finalized-card"><b>Automatic decision: ${escapeHtml(c.st)}</b><p>${escapeHtml((c.decisionReasons || []).join(', '))}</p><p>Image screening result. Evidence rejections require resubmission; policy and unreadable identity findings are advisory.</p><button type="button" class="btn" id="btn-reopen">Optional technician re-evaluation</button></div>`:resolved&&!c.reopened?`<div class="resolution-finalized-card"><b>Technician decision: ${escapeHtml(c.st)}</b><p>${escapeHtml(c.resolvedReason)}</p>
      <p>Operator: ${escapeHtml(c.resolvedOperator)} • ${escapeHtml(c.resolvedTime)}</p><code>${escapeHtml(c.resolvedHash)}</code>
      <button type="button" class="btn" id="btn-reopen">Re-evaluate determination</button></div>`:
      `<div class="technician-action-panel"><h3>Technician determination</h3><p>Local operator TECH-402. Record your actual observations before deciding.</p>
      <div class="reason-quick-chips">
      <button type="button" class="r-chip" data-reason="Observed condition: no visible physical damage in the supplied photographs. Policy eligibility reviewed manually.">No visible damage</button>
      <button type="button" class="r-chip" data-reason="Observed condition: visible physical damage. Location and applicable policy: ">Visible damage</button>
      <button type="button" class="r-chip" data-reason="The serial identifier is unreadable in the supplied photographs. Additional evidence is required.">Unreadable serial</button>
      </div><textarea id="rs" class="input-area" rows="3" maxlength="2000" placeholder="Required inspection findings"></textarea>
      <div class="acts"><button type="button" class="btn g" id="btn-approve">Approve Return</button><button type="button" class="btn r" id="btn-reject">Reject Return</button></div><p id="e2" class="err"></p></div>`}
    <p>Intake audit SHA-256: <code>${escapeHtml(c.ledgerHash)}</code></p><button type="button" class="btn btn-outline" id="btn-export">Download review record</button>`;
  $$('.thumb-btn',$('#d')).forEach(btn=>btn.onclick=()=>{c.selectedSlot=Number(btn.dataset.slot);renderDetails();});
  if ($('#btn-reopen')) $('#btn-reopen').onclick=()=>{c.reopened=true;renderDetails();};
  $$('.r-chip',$('#d')).forEach(chip=>chip.onclick=()=>{$('#rs').value=chip.dataset.reason;$('#rs').focus();});
  if ($('#btn-approve')) $('#btn-approve').onclick=()=>executeOverride('Approved');
  if ($('#btn-reject')) $('#btn-reject').onclick=()=>executeOverride('Rejected');
  $('#btn-export').disabled=tampered;
  $('#btn-export').onclick=()=>historicalCase?downloadHistoricalCase(c.id,historicalBlockHash):downloadCase(c.id);
  if($('#btn-current-case'))$('#btn-current-case').onclick=()=>{historicalCase=null;renderQueue();renderDetails();};
}
async function executeOverride(decision) {
  if (saving) return;
  const c=CASES.find(row=>row.id===activeCaseId);
  if (!c || !$('#rs') || historicalCase || c._integrity==='TAMPERED') return;
  const reason=$('#rs').value.trim();
  if(reason.length<3){$('#e2').textContent='Enter your inspection findings (at least 3 characters).';return;}
  saving=true; $('#btn-approve').disabled=true; $('#btn-reject').disabled=true;
  try {
    const data=await fetchJson(getGatewayUrl(`/api/v1/cases/${encodeURIComponent(c.id)}/decision`), {
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,reason,operator:'TECH-402'})},15000);
    CASES[CASES.indexOf(c)]=data.case;
    currentFilter='all'; activeCaseId=data.case.id;
    $$('.q-tab').forEach(tab=>tab.classList.toggle('active',tab.dataset.filter==='all'));
    renderQueue();renderDetails();showToast(`Decision saved: ${data.decision}`,'success');
    try{await syncBackendLedger();}catch{showToast('Decision saved; audit refresh unavailable. Use Refresh cases and audit.','warning');}
  } catch(error){if($('#e2'))$('#e2').textContent=`Not saved: ${error.message}`;showToast('Decision was not confirmed','error');}
  finally{saving=false;if($('#btn-approve'))$('#btn-approve').disabled=false;if($('#btn-reject'))$('#btn-reject').disabled=false;}
}
function renderAuditLog() {
  const approved=auditLedger.filter(a=>a.disposition==='APPROVE');
  const rejected=auditLedger.filter(a=>a.disposition==='REJECT');
  count('audit-all-count',auditLedger.length); count('audit-approved-count',approved.length); count('audit-rejected-count',rejected.length);
  count('history-badge',`${auditLedger.length} AUDIT EVENTS (LATEST 500)`);
  const rows=auditLedger.filter(a=>currentAuditFilter==='all'|| currentAuditFilter==='approved'&&a.disposition==='APPROVE'||currentAuditFilter==='rejected'&&a.disposition==='REJECT');
  $('#log').innerHTML=rows.length?rows.map((a,i)=>`<button class="audit-item interactive-audit-card" type="button" data-event="${i}">
    <div><b>${escapeHtml(a.case_id)} • ${escapeHtml(a.disposition)}</b><p>${escapeHtml(a.timestamp)}</p>
    <p>${escapeHtml(a.reason || a.cited_clause)}</p><code>${escapeHtml(a.block_hash)}</code></div></button>`).join(''):'<p>No matching audit events.</p>';
  $$('#log [data-event]').forEach(btn=>btn.onclick=async()=>{
    const event=rows[Number(btn.dataset.event)];
    if(event.case_hash){
      try{
        const record=await fetchJson(getGatewayUrl(`/api/v1/cases/${encodeURIComponent(event.case_id)}/history/${encodeURIComponent(event.block_hash)}`),{},15000);
        historicalCase=record.case;historicalBlockHash=event.block_hash;
      }catch(error){showToast(error.message,'error');return;}
    }else{
      historicalCase=null;
      if(!CASES.some(c=>c.id===event.case_id))return showToast('Legacy event has no verifiable historical dossier.','warning');
      showToast('Legacy event: displaying the current dossier; no historical snapshot exists.','warning');
    }
    activeCaseId=event.case_id;currentFilter='all';searchQuery='';$('#q-search').value='';
    $$('.q-tab').forEach(tab=>tab.classList.toggle('active',tab.dataset.filter==='all'));
    renderQueue();renderDetails();$('#d').scrollIntoView({behavior:'smooth'});
  });
}
async function syncBackendLedger() {
  const [cases,ledger,verification]=await Promise.all([
    fetchJson(getGatewayUrl('/api/v1/cases'),{},15000),
    fetchJson(getGatewayUrl('/api/v1/ledger?limit=500'),{},15000),
    fetchJson(getGatewayUrl('/api/v1/ledger/verify'),{},15000)]);
  CASES=cases.cases.sort((a,b)=>(Number(b.v)*Number(b.r))-(Number(a.v)*Number(a.r)));
  auditLedger=[...ledger.recent_blocks].reverse();
  $('#audit-integrity').textContent=verification.valid?`Audit chain verified (${verification.blocks_verified} blocks). Bound dossiers and snapshots verified; ${verification.legacy_dossiers?.length || 0} legacy dossier(s) have no historical binding.`:'Audit chain or dossier verification FAILED';
  $('#audit-integrity').style.color=verification.valid?'var(--success-text)':'var(--danger-text)';
  renderQueue();renderDetails();renderAuditLog();
}
async function purgeAllAudits() {
  if(!confirm('Delete all local cases, audit history, and image fingerprints? This cannot be undone.'))return;
  try {
    await fetchJson(getGatewayUrl('/api/v1/reset'),{method:'POST'},15000);
    for(const key of ['smartrma_cases','smartrma_audit_history','smartrma_active_case_id'])try{localStorage.removeItem(key);}catch{}
    activeCaseId=null;historicalCase=null;await syncBackendLedger();showToast('Local workspace cleared','info');
  } catch(error){showToast(`Reset was not confirmed: ${error.message}`,'error');}
}
document.addEventListener('keydown',event=>{
  if(saving||event.target.matches('input,textarea,select,button'))return;
  const rows=filteredCases();const index=rows.findIndex(c=>c.id===activeCaseId);
  if(['ArrowDown','ArrowUp'].includes(event.key)&&rows.length){event.preventDefault();historicalCase=null;activeCaseId=rows[Math.max(0,Math.min(rows.length-1,index+(event.key==='ArrowDown'?1:-1)))].id;renderQueue();renderDetails();}
  else if(event.key.toLowerCase()==='a'&&$('#rs'))executeOverride('Approved');
  else if(event.key.toLowerCase()==='r'&&$('#rs'))executeOverride('Rejected');
});
document.addEventListener('DOMContentLoaded',async()=>{
  try{activeCaseId=localStorage.getItem('smartrma_active_case_id');}catch{}
  if(activeCaseId){currentFilter='all';$$('.q-tab').forEach(tab=>tab.classList.toggle('active',tab.dataset.filter==='all'));}
  $$('.q-tab').forEach(tab=>tab.onclick=()=>{historicalCase=null;currentFilter=tab.dataset.filter;$$('.q-tab').forEach(t=>t.classList.toggle('active',t===tab));renderQueue();renderDetails();});
  $$('.audit-filter-btn').forEach(tab=>tab.onclick=()=>{currentAuditFilter=tab.dataset.filter;$$('.audit-filter-btn').forEach(t=>t.classList.toggle('active',t===tab));renderAuditLog();});
  $('#q-search').oninput=()=>{historicalCase=null;searchQuery=$('#q-search').value.trim().toLowerCase();renderQueue();renderDetails();};
  $('#btn-purge-audits').onclick=purgeAllAudits;
  $('#btn-refresh').onclick=async()=>{try{historicalCase=null;await syncBackendLedger();}catch(error){showToast(error.message,'error');}};
  try{await syncBackendLedger();}catch(error){$('#d').textContent=`Cannot load cases: ${error.message}`;showToast('Gateway unavailable. No case data loaded.','error');}
});
