// SmartRMA Core Utilities & Theme Engine
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

// Theme Management (Default: Dark, with Light toggle)
(function initTheme() {
  const saved = localStorage.getItem('smartrma-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('smartrma-theme', next);
  updateThemeIcon();
}

function updateThemeIcon() {
  const btn = $('#theme-toggle');
  if (!btn) return;
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
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
