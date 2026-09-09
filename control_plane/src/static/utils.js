/**
 * LineagIQ Control Plane - Shared DOM & Formatting Utilities
 */

export const getEl = (id) => (typeof document !== 'undefined' ? document.getElementById(id) : null);

export const getVal = (id, fallback = '') => {
  const el = getEl(id);
  return el ? (el.value !== undefined ? el.value.trim() : fallback) || fallback : fallback;
};

export function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function parseNodeProperties(node) {
  if (!node || !node.properties) return {};
  if (typeof node.properties === 'object') return node.properties;
  if (typeof node.properties === 'string') {
    try {
      return JSON.parse(node.properties);
    } catch (e) {
      return { raw: node.properties };
    }
  }
  return {};
}

export function showToast(message, duration = 2800) {
  if (typeof document === 'undefined') return;
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = 'toast-notification';
  toast.innerText = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-fadeout');
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }, duration);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    getEl,
    getVal,
    escapeHtml,
    parseNodeProperties,
    showToast
  };
}
