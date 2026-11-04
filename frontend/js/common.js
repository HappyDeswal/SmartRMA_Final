// SmartRMA Core Utilities & Theme Engine
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

// Theme Management (Default: Dark, with Light toggle)
(function initTheme() {
  let saved = 'light';
  try { saved = localStorage.getItem('smartrma-theme') || 'light'; } catch {}
  document.documentElement.setAttribute('data-theme', saved);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('smartrma-theme', next); } catch {}
  updateThemeIcon();
}

function updateThemeIcon() {
  const btn = $('#theme-toggle');
  if (!btn) return;
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  btn.innerHTML = current === 'dark' 
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
}

// Global Toast Notification System
function showToast(message, type = 'info', duration = 3200) {
  let container = $('#toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : type === 'warning' ? '⚠' : 'ℹ';
  const iconSpan = document.createElement('span');
  iconSpan.className = 'toast-icon';
  iconSpan.textContent = icon;

  const textSpan = document.createElement('span');
  textSpan.className = 'toast-text';
  textSpan.textContent = String(message || '');

  toast.appendChild(iconSpan);
  toast.appendChild(textSpan);
  container.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add('visible'));

  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

document.addEventListener('DOMContentLoaded', () => {
  updateThemeIcon();
  const btn = $('#theme-toggle');
  if (btn) btn.onclick = toggleTheme;
});

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
}
function getGatewayUrl(path) { return `http://${location.hostname || '127.0.0.1'}:8000${path}`; }
async function fetchJson(url, options = {}, timeout = 330000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, {...options, signal: controller.signal});
    const data = await response.json();
    if (!response.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data.error || 'Request failed');
      throw new Error(detail);
    }
    return data;
  } finally { clearTimeout(timer); }
}
function imageSource(source) {
  if (typeof source !== 'string') return '';
  // Only validated embedded rasters and project asset paths can be inserted into HTML.
  const datasetPath = /^dataset\/(damaged|undamaged)\/[a-z0-9_-]+\/[a-z0-9_-]+\.(jpg|jpeg|png|webp|bmp)$/i.test(source);
  const tierDatasetPath = /^dataset\/T[1-4]\/[a-z0-9_-]+\.(jpg|jpeg|png|webp|bmp)$/i.test(source);
  return datasetPath || tierDatasetPath || /^data:image\/(jpeg|png|webp|bmp);base64,[a-z0-9+/=]+$/i.test(source) || /^(assets|approve|unapproved)\/[\w.-]+\.(jpg|jpeg|png|webp|bmp)$/i.test(source) ? source : '';
}
function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob); link.download = filename;
  link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
async function downloadCase(caseId) {
  try {
    const data = await fetchJson(getGatewayUrl(`/api/v1/cases/${encodeURIComponent(caseId)}/export`));
    downloadJson(data, `${caseId}-review-record.json`);
  } catch (error) { showToast(error.message, 'error'); }
}
async function downloadHistoricalCase(caseId, blockHash) {
  try {
    const data = await fetchJson(getGatewayUrl(`/api/v1/cases/${encodeURIComponent(caseId)}/history/${encodeURIComponent(blockHash)}`));
    downloadJson(data, `${caseId}-${blockHash.slice(0,12)}-historical-record.json`);
  } catch (error) { showToast(error.message, 'error'); }
}
