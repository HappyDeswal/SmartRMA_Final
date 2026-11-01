// Customer intake and informational chat. All decisions come from the backend.
const SLOTS_CONFIG = [
  {name:'Full Product Front', icon:'🔲'}, {name:'Full Product Back', icon:'🛡️'},
  {name:'Contacts & Connectors', icon:'⚡'}, {name:'Damage or Detail View', icon:'🔌'},
  {name:'Serial Barcode Label', icon:'🏷️'}
];
const ph = Array(5).fill(null);
const history = [];
let intakeBusy = false;
let chatBusy = false;
const getTier = value => value < 300 ? 'T1' : value <= 1000 ? 'T2' : value <= 2500 ? 'T3' : 'T4';
const TIERS = {
  T1:'Under $300: automatic image screening; clean images need risk under 30 and at least 85% confidence.',
  T2:'$300–$1,000: automatic approval/rejection; clean approval needs at least 85% confidence.',
  T3:'Over $1,000–$2,500: automatic approval/rejection; clean approval needs at least 95% confidence.',
  T4:'Over $2,500: mandatory technician review.'
};
function updateTierDisplay() {
  const value = Number($('#val').value);
  $('#tp').textContent = value > 0 ? `${getTier(value)} — ${TIERS[getTier(value)]}` : 'Enter declared value to compute SLA tier policy';
}
function saveCurrentIntakeDraft() {
  // Text draft only: original photo data can exceed browser storage quotas.
  const draft = Object.fromEntries(['oid','ser','val','mfg-select','model-line','rsn'].map(id => [id, $('#'+id).value]));
  try { sessionStorage.setItem('smartrma_intake_text', JSON.stringify(draft)); } catch {}
}
function readOriginalImage(file) {
  return new Promise((resolve, reject) => {
    if (!/^image\/(jpeg|png|webp|bmp)$/.test(file.type)) return reject(new Error('Use JPEG, PNG, WebP, or BMP photos.'));
    if (file.size > 15 * 1024 * 1024) return reject(new Error('Each photo must be at most 15MB.'));
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Unable to read the photo.'));
    reader.readAsDataURL(file); // Preserve original EXIF for the gateway audit.
  });
}
function initSlots() {
  $('#slots').innerHTML = SLOTS_CONFIG.map((slot,i) => `<label class="slot" id="sl${i}">
    <input type="file" accept="image/jpeg,image/png,image/webp,image/bmp" hidden data-i="${i}">
    <div class="slot-meta"><span class="slot-label">${slot.name}</span><span class="slot-status mono" id="sl-status-${i}">Awaiting Upload</span></div>
    <div class="slot-icon-guide">${slot.icon}</div></label>`).join('');
  $$('#slots input').forEach(input => input.onchange = async () => {
    if (!input.files[0]) return;
    try {
      const source = await readOriginalImage(input.files[0]);
      ph[Number(input.dataset.i)] = source;
      const slot = $('#sl'+input.dataset.i);
      slot.classList.add('on'); slot.style.backgroundImage = `url("${source}")`;
      $('#sl-status-'+input.dataset.i).textContent = 'Uploaded';
      updatePhotoCount();
    } catch (error) { showToast(error.message, 'error'); input.value = ''; }
  });
  updatePhotoCount();
}
function updatePhotoCount() { $('#cnt').textContent = `${ph.filter(Boolean).length} of 5 views uploaded`; }
function appendMessage(text, outgoing=false, html=false) {
  const row = document.createElement('div'); row.className = `wa-msg-row ${outgoing?'out':'in'}`;
  const bubble = document.createElement('div'); bubble.className = 'wa-bubble';
  if (html) bubble.innerHTML = text; else { bubble.textContent = text; bubble.style.whiteSpace = 'pre-wrap'; }
  row.append(bubble); $('#wa-messages').append(row);
  $('#wa-body').scrollTop = $('#wa-body').scrollHeight;
}
function showBotTyping(active) { $('#wa-status').textContent = active ? 'Local model processing…' : 'Informational assistant • Local Ollama only'; }
window.askPresetQuestion = text => { $('#wa-input').value = text; handleChatSubmit(); };
window.handleChatSubmit = async event => {
  event?.preventDefault();
  const message = $('#wa-input').value.trim();
  if (!message || chatBusy) return;
  if (message.length > 1000) return showToast('Keep questions under 1,000 characters.', 'warning');
  chatBusy = true; $('#wa-send').disabled = true; $('#wa-input').value = '';
  appendMessage(message,true); showBotTyping(true);
  try {
    const data = await fetchJson('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message, history:history.slice(-6)})}, 210000);
    history.push({role:'user',content:message}, {role:'assistant',content:data.reply.slice(0,1000)});
    const sources = data.sources.map(source => `<div>📄 ${escapeHtml(source.document)} — page ${Number(source.page)}</div>`).join('');
    appendMessage(`<div style="white-space:pre-wrap">${escapeHtml(data.reply)}</div><small>Local model: ${escapeHtml(data.model_used)}</small>${sources}`,false,true);
  } catch (error) { appendMessage(`Unable to answer: ${error.message}. No claim or representative ticket was created.`); }
  finally { chatBusy=false; $('#wa-send').disabled=false; showBotTyping(intakeBusy); }
};
async function handleTriageSubmit(event) {
  event.preventDefault();
  if (intakeBusy) return;
  const form = $('#f');
  if (!form.reportValidity()) return;
  const images = ph.map((source,slot) => source ? {slot,name:SLOTS_CONFIG[slot].name,image_b64:source} : null).filter(Boolean);
  if (!images.length) { $('#err').textContent='Upload at least one inspection photo.'; return; }
  const payload = {order_id:$('#oid').value.trim(), serial_number:$('#ser').value.trim() || 'UNVERIFIED',
    product_value:Number($('#val').value), manufacturer:$('#mfg-select').value,
    model_name:$('#model-line').value.trim(), symptom_description:$('#rsn').value.trim(), images};
  intakeBusy=true; $('#btn-submit').disabled=true; $('#btn-reset').disabled=true; $('#err').textContent='';
  $$('#f input, #f select, #f textarea').forEach(input => input.disabled=true);
  showBotTyping(true); $$('#slots .slot').forEach(slot => slot.classList.add('scanning'));
  try {
    const data = await fetchJson(getGatewayUrl('/api/v1/intake'), {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const c = data.case;
    try { localStorage.setItem('smartrma_active_case_id',c.id); sessionStorage.removeItem('smartrma_intake_text'); } catch {}
    const audits = data.security_audit;
    const card = `<div class="wa-decision-card"><h3>${escapeHtml(c.id)} — AI suggestion: ${escapeHtml(data.disposition)}</h3>
      <p>${escapeHtml(c.p)} • ${escapeHtml(c.t)} • $${c.v}</p>
      <p>Risk: ${c.r==null?'Unassessed':c.r+'/100'} • Model confidence estimate: ${c.visionTelemetry.assessment_available?c.conf+'%':'Unavailable'} • Anomaly estimate: ${c.a==null?'Unassessed':c.a.toFixed(2)}</p>
      <p style="white-space:pre-wrap">${escapeHtml(c.visionTelemetry.visual_findings)}</p>
      <p>${audits.images_verified} photos audited. Similar prior photo: ${audits.has_duplicate_phash?'flagged':'not found'}.
      Editing metadata: ${audits.has_tampered_exif?'present':'not found'}. EXIF does not prove authenticity.</p>
      <p>Policy suggestion: ${escapeHtml(c.policyGrounding.verdict)}<br>${escapeHtml(c.cl)}<br>
      Source: ${escapeHtml(c.src || 'No applicable indexed source')}${c.policyGrounding.page?` (page ${c.policyGrounding.page})`:''}</p>
      <p>Local model: ${escapeHtml(c.visionTelemetry.model_used || 'Unavailable')}</p>
      <small>Audit SHA-256: ${escapeHtml(c.ledgerHash)}</small>
      <p>Decision reasons: ${escapeHtml((data.decision_reasons || []).join(", "))}</p><p>All model findings require technician verification.</p>
      <a class="wa-action-btn" href="review.html">Open Technician Review</a>
      <button type="button" class="wa-action-btn" id="download-${c.id}">Download review record</button></div>`;
    appendMessage(card,false,true); $('#download-'+c.id).onclick=()=>downloadCase(c.id);
    $('#intake-stage').textContent=`SAVED: ${c.id}`;
    showToast(`Case saved: ${c.st}`, 'success');
  } catch (error) {
    $('#err').textContent=`Submission was not confirmed: ${error.message}. Check the review queue before retrying.`;
    showToast('Triage submission was not confirmed', 'error');
  } finally {
    intakeBusy=false; $('#btn-submit').disabled=false; $('#btn-reset').disabled=false;
    $$('#f input, #f select, #f textarea').forEach(input => input.disabled=false);
    $$('#slots .slot').forEach(slot => slot.classList.remove('scanning')); showBotTyping(chatBusy);
  }
}
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const draft=JSON.parse(sessionStorage.getItem('smartrma_intake_text') || 'null');
    if (draft) Object.entries(draft).forEach(([id,value])=>{if ($('#'+id)) $('#'+id).value=value;});
  } catch {}
  initSlots(); updateTierDisplay(); $('#f').onsubmit=handleTriageSubmit;
  $('#f').addEventListener('input',()=>{updateTierDisplay();saveCurrentIntakeDraft();});
  $('#btn-reset').onclick=()=>{$('#f').reset();ph.fill(null);initSlots();updateTierDisplay();$('#err').textContent='';try{sessionStorage.removeItem('smartrma_intake_text');}catch{}};
  $('#wa-start-time').textContent=new Date().toLocaleTimeString();
  try {
    const data=await fetchJson('/api/policies'); $('#policy-count').textContent=`${data.catalog.length} documents indexed`;
    const brands=new Set(data.catalog.map(doc=>doc.manufacturer.toLowerCase()));
    $$('#mfg-select option').forEach(option=>{if(option.value&&!brands.has(option.value.toLowerCase()))option.textContent+=' — manual policy review';});
  } catch { $('#policy-count').textContent='Policy index unavailable'; }
});
