/**
 * LineagIQ Control Plane - AI Assistant & Chat Module
 */

import { sendChat } from './api.js';
import { getEl, getVal, escapeHtml, showToast } from './utils.js';

let chatDockMode = 'dynamic'; // 'dynamic' | 'right' | 'left'
let onHighlightTargetNode = null;

export function setHighlightTargetNodeCallback(fn) {
  onHighlightTargetNode = fn;
}

export function updateChatDrawerPosition() {
  const drawer = getEl('chat-drawer');
  if (!drawer) return;

  // On mobile devices (<= 768px), drawer is positioned via responsive CSS bottom sheet
  if (typeof window !== 'undefined' && window.innerWidth <= 768) {
    drawer.style.left = '';
    drawer.style.right = '';
    return;
  }

  if (chatDockMode === 'right') {
    if (drawer.classList) {
      drawer.classList.remove('dock-left');
      drawer.classList.add('dock-right');
    }
    drawer.style.right = '16px';
    drawer.style.left = 'auto';
    return;
  }
  if (chatDockMode === 'left') {
    if (drawer.classList) {
      drawer.classList.remove('dock-right');
      drawer.classList.add('dock-left');
    }
    drawer.style.left = '16px';
    drawer.style.right = 'auto';
    return;
  }

  // Dynamic mode: when Node Properties is opened, move slightly left so it docks to Node Properties right side;
  // when closed, return smoothly to right edge (16px).
  if (drawer.classList) {
    drawer.classList.remove('dock-left');
    drawer.classList.remove('dock-right');
  }
  drawer.style.left = 'auto';

  const sidebar = getEl('sidebar');
  const isSidebarVisible = sidebar && sidebar.style.display !== 'none' && (sidebar.offsetWidth > 0 || sidebar.offsetWidth === undefined);
  if (isSidebarVisible) {
    const sidebarWidth = (sidebar.offsetWidth && sidebar.offsetWidth > 0) ? sidebar.offsetWidth : 400;
    drawer.style.right = `${sidebarWidth + 16}px`;
  } else {
    drawer.style.right = '16px';
  }
}

export function toggleChatDockMode() {
  const dockBtn = getEl('dock-btn');
  if (chatDockMode === 'dynamic') {
    chatDockMode = 'right';
    if (dockBtn) dockBtn.title = 'AI Assistant locked to right edge (Click to dock left)';
    showToast('AI Assistant locked to right edge');
  } else if (chatDockMode === 'right') {
    chatDockMode = 'left';
    if (dockBtn) dockBtn.title = 'AI Assistant docked to left edge (Click for dynamic mode)';
    showToast('AI Assistant docked to left');
  } else {
    chatDockMode = 'dynamic';
    if (dockBtn) dockBtn.title = 'AI Assistant dynamic positioning (Docks next to Node Properties when open, right edge when closed)';
    showToast('AI Assistant dynamic positioning active (Docks next to Node Properties)');
  }
  updateChatDrawerPosition();
}

export function toggleChatDrawer() {
  const drawer = getEl('chat-drawer');
  if (!drawer) return;
  const willShow = (drawer.style.display === 'none' || !drawer.style.display);
  drawer.style.display = willShow ? 'flex' : 'none';

  const backdrop = getEl('drawer-backdrop');
  if (backdrop && typeof window !== 'undefined' && window.innerWidth <= 768) {
    backdrop.style.display = willShow ? 'block' : 'none';
  }

  if (willShow) {
    updateChatDrawerPosition();
    const inputEl = getEl('chat-input');
    if (inputEl && (typeof window === 'undefined' || window.innerWidth > 768)) {
      setTimeout(() => inputEl.focus(), 150);
    }
  }
}

export function toggleChatSettings() {
  const panel = getEl('chat-settings');
  if (panel) panel.style.display = (panel.style.display === 'none' || !panel.style.display) ? 'flex' : 'none';
}

export function setOllamaConfig() {
  const urlEl = getEl('cfg-base-url');
  const modelEl = getEl('cfg-model');
  const keyEl = getEl('cfg-api-key');
  if (urlEl) urlEl.value = 'http://localhost:11434/v1';
  if (modelEl) modelEl.value = 'llama3';
  if (keyEl) keyEl.value = 'ollama';
  saveLlmSettings();
  showToast('Configured for local Ollama (http://localhost:11434/v1, model: llama3)');
}

export function setOpenAiConfig() {
  const urlEl = getEl('cfg-base-url');
  const modelEl = getEl('cfg-model');
  const keyEl = getEl('cfg-api-key');
  if (urlEl) urlEl.value = '';
  if (modelEl) modelEl.value = '';
  if (keyEl) keyEl.value = '';
  saveLlmSettings();
  showToast('Reset to default OpenAI / Gemini cloud config');
}

export function saveLlmSettings() {
  const apiKey = getVal('cfg-api-key');
  const baseUrl = getVal('cfg-base-url');
  const model = getVal('cfg-model');
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('lineagiq_api_key', apiKey);
    localStorage.setItem('lineagiq_base_url', baseUrl);
    localStorage.setItem('lineagiq_model', model);
  }
}

export function loadLlmSettings() {
  if (typeof localStorage === 'undefined') return;
  const apiKey = localStorage.getItem('lineagiq_api_key') || '';
  const baseUrl = localStorage.getItem('lineagiq_base_url') || '';
  const model = localStorage.getItem('lineagiq_model') || '';

  const keyEl = getEl('cfg-api-key');
  const urlEl = getEl('cfg-base-url');
  const modelEl = getEl('cfg-model');

  if (keyEl) keyEl.value = apiKey;
  if (urlEl) urlEl.value = baseUrl;
  if (modelEl) modelEl.value = model;
}

export function applySuggestedPrompt(promptText) {
  const inputEl = getEl('chat-input');
  if (inputEl) inputEl.value = promptText;
  sendChatMessage();
}

export async function sendChatMessage() {
  const inputEl = getEl('chat-input');
  if (!inputEl) return;
  const message = inputEl.value.trim();
  if (!message) return;

  const tenantId = getVal('tenant-input', 'demo_tenant');
  const dataPath = getVal('data-path-input');

  const apiKey = getVal('cfg-api-key') || undefined;
  const baseUrl = getVal('cfg-base-url') || undefined;
  const model = getVal('cfg-model') || undefined;

  const messagesContainer = getEl('chat-messages');
  if (!messagesContainer) return;

  const userMsgDiv = document.createElement('div');
  userMsgDiv.className = 'chat-msg chat-msg-user';
  userMsgDiv.innerHTML = `<div class="msg-bubble">${escapeHtml(message)}</div>`;
  messagesContainer.appendChild(userMsgDiv);

  inputEl.value = '';
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  const aiLoadingDiv = document.createElement('div');
  aiLoadingDiv.className = 'chat-msg chat-msg-ai';
  aiLoadingDiv.innerHTML = `<div class="msg-bubble"><em>Analyzing Knowledge Graph...</em></div>`;
  messagesContainer.appendChild(aiLoadingDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  try {
    const data = await sendChat(tenantId, dataPath, message, {
      apiKey,
      baseUrl,
      model
    });

    const bubble = aiLoadingDiv.querySelector('.msg-bubble');
    if (bubble) bubble.innerHTML = data.reply || '';

    if (data.target_node_id && typeof onHighlightTargetNode === 'function') {
      onHighlightTargetNode(data.target_node_id);
    }
  } catch (err) {
    const bubble = aiLoadingDiv.querySelector('.msg-bubble');
    if (bubble) bubble.innerHTML = `<span style="color: var(--accent-rose);">Error: ${escapeHtml(err.message)}</span>`;
  }

  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    updateChatDrawerPosition,
    toggleChatDockMode,
    toggleChatDrawer,
    toggleChatSettings,
    setOllamaConfig,
    setOpenAiConfig,
    saveLlmSettings,
    loadLlmSettings,
    applySuggestedPrompt,
    sendChatMessage,
    setHighlightTargetNodeCallback
  };
}
