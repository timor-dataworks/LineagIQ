/**
 * LineagIQ Control Plane - Time Travel & Diff Module
 */

import { fetchTimeline, fetchTimeDiff } from './api.js';
import { getEl, getVal, escapeHtml } from './utils.js';

let availableTimestamps = [];
let currentAsOfTimestamp = null;
let lastDiffResult = null;
let timelineDebounceTimer = null;

let onReloadGraphCallback = null;
let onApplyDiffVisualsCallback = null;
let onOpenChatWithPromptCallback = null;
let onGetSelectedNodeIdCallback = null;

export function setTimelineCallbacks({ reloadGraph, applyDiffVisuals, openChatWithPrompt, getSelectedNodeId }) {
  if (reloadGraph) onReloadGraphCallback = reloadGraph;
  if (applyDiffVisuals) onApplyDiffVisualsCallback = applyDiffVisuals;
  if (openChatWithPrompt) onOpenChatWithPromptCallback = openChatWithPrompt;
  if (getSelectedNodeId) onGetSelectedNodeIdCallback = getSelectedNodeId;
}

export function getCurrentAsOfTimestamp() {
  return currentAsOfTimestamp;
}

export function setCurrentAsOfTimestamp(ts) {
  currentAsOfTimestamp = ts;
}

export async function loadTimeline() {
  const tenantId = getVal('tenant-input', 'demo_tenant');
  const dataPath = getVal('data-path-input');

  try {
    const data = await fetchTimeline(tenantId, dataPath);
    availableTimestamps = data.timestamps || [];

    const panel = getEl('timeline-panel');
    const slider = getEl('timeline-slider');
    const label = getEl('timeline-label');

    if (panel && slider && availableTimestamps.length > 1) {
      panel.style.display = 'flex';
      slider.min = 0;
      slider.max = availableTimestamps.length - 1;
      slider.step = 1;

      if (currentAsOfTimestamp === null) {
        slider.value = availableTimestamps.length - 1;
        const lastItem = availableTimestamps[availableTimestamps.length - 1];
        if (label) label.innerText = `LIVE (v${lastItem ? lastItem.version : 'Latest'})`;
      } else {
        const matchingIdx = availableTimestamps.findIndex(t => t.timestamp === currentAsOfTimestamp);
        if (matchingIdx !== -1) {
          slider.value = matchingIdx;
          const currentItem = availableTimestamps[matchingIdx];
          if (label) label.innerHTML = `v${currentItem.version} <span style="color: var(--accent-cyan);">${currentItem.timestamp}</span>`;
        } else {
          slider.value = availableTimestamps.length - 1;
          currentAsOfTimestamp = null;
          if (label) label.innerText = 'LIVE (Latest)';
        }
      }
    } else if (panel) {
      panel.style.display = 'none';
    }
  } catch (err) {
    console.warn("Timeline fetch error:", err);
  }
}

export function onTimelineSliderChange(val) {
  const idx = parseInt(val, 10);
  const label = getEl('timeline-label');
  const maxIdx = availableTimestamps.length - 1;

  if (isNaN(idx) || maxIdx < 0) return;

  const clampedIdx = Math.max(0, Math.min(idx, maxIdx));

  if (clampedIdx === maxIdx) {
    currentAsOfTimestamp = null;
    const lastItem = availableTimestamps[maxIdx];
    if (label) label.innerText = `LIVE (v${lastItem ? lastItem.version : 'Latest'})`;
  } else {
    const item = availableTimestamps[clampedIdx];
    if (item) {
      currentAsOfTimestamp = item.timestamp;
      if (label) label.innerHTML = `v${item.version} <span style="color: var(--accent-cyan);">${item.timestamp}</span>`;
    }
  }

  if (timelineDebounceTimer) clearTimeout(timelineDebounceTimer);
  timelineDebounceTimer = setTimeout(() => {
    if (typeof onReloadGraphCallback === 'function') {
      onReloadGraphCallback(false);
    }
  }, 200);
}

export function resetTimelineLive() {
  const slider = getEl('timeline-slider');
  const label = getEl('timeline-label');
  const maxIdx = availableTimestamps.length > 0 ? availableTimestamps.length - 1 : 0;
  if (slider) slider.value = maxIdx;
  currentAsOfTimestamp = null;
  const lastItem = availableTimestamps[maxIdx];
  if (label) label.innerText = `LIVE (v${lastItem ? lastItem.version : 'Latest'})`;
  if (typeof onReloadGraphCallback === 'function') {
    onReloadGraphCallback(false);
  }
}

export function openTimeDiffModal() {
  const modal = getEl('time-diff-modal');
  if (modal) modal.style.display = 'flex';
  populateDiffDropdowns();
}

export function closeTimeDiffModal() {
  const modal = getEl('time-diff-modal');
  if (modal) modal.style.display = 'none';
}

export function populateDiffDropdowns() {
  const sel1 = getEl('diff-t1-select');
  const sel2 = getEl('diff-t2-select');
  if (!sel1 || !sel2) return;
  sel1.innerHTML = '';
  sel2.innerHTML = '';

  if (!availableTimestamps || availableTimestamps.length === 0) {
    sel1.innerHTML = '<option value="">No historical commits available</option>';
    sel2.innerHTML = '<option value="">No historical commits available</option>';
    return;
  }

  availableTimestamps.forEach((item) => {
    const opt1 = document.createElement('option');
    opt1.value = item.timestamp;
    opt1.innerText = `v${item.version} - ${item.timestamp}`;
    sel1.appendChild(opt1);

    const opt2 = document.createElement('option');
    opt2.value = item.timestamp;
    opt2.innerText = `v${item.version} - ${item.timestamp}`;
    sel2.appendChild(opt2);
  });

  sel1.selectedIndex = 0;
  sel2.selectedIndex = availableTimestamps.length - 1;

  const nodeInput = getEl('diff-node-input');
  const activeId = onGetSelectedNodeIdCallback ? onGetSelectedNodeIdCallback() : null;
  if (activeId && nodeInput) {
    nodeInput.value = activeId;
  }
}

export async function executeTimeDiff() {
  const t1 = getVal('diff-t1-select');
  const t2 = getVal('diff-t2-select');
  const nodeId = getVal('diff-node-input');
  const tenantId = getVal('tenant-input', 'demo_tenant');
  const dataPath = getVal('data-path-input');

  if (!t1 || !t2) {
    alert("Please select baseline (T1) and compare (T2) timestamps.");
    return;
  }

  try {
    const data = await fetchTimeDiff(tenantId, dataPath, nodeId, t1, t2);
    lastDiffResult = data;

    const diff = data.diff || {};
    const addedNodes = diff.added_nodes || [];
    const removedNodes = diff.removed_nodes || [];
    const modifiedNodes = diff.modified_nodes || [];
    const addedEdges = diff.added_edges || [];
    const removedEdges = diff.removed_edges || [];

    const cntAdded = getEl('diff-count-added');
    const cntRemoved = getEl('diff-count-removed');
    const cntModified = getEl('diff-count-modified');
    const cntEdges = getEl('diff-count-edges');

    if (cntAdded) cntAdded.innerText = addedNodes.length;
    if (cntRemoved) cntRemoved.innerText = removedNodes.length;
    if (cntModified) cntModified.innerText = modifiedNodes.length;
    if (cntEdges) cntEdges.innerText = addedEdges.length + removedEdges.length;

    const bdgAdded = getEl('badge-tab-added');
    const bdgRemoved = getEl('badge-tab-removed');
    const bdgModified = getEl('badge-tab-modified');
    const bdgEdges = getEl('badge-tab-edges');

    if (bdgAdded) bdgAdded.innerText = addedNodes.length;
    if (bdgRemoved) bdgRemoved.innerText = removedNodes.length;
    if (bdgModified) bdgModified.innerText = modifiedNodes.length;
    if (bdgEdges) bdgEdges.innerText = addedEdges.length + removedEdges.length;

    const addedContainer = getEl('diff-tab-added');
    if (addedContainer) {
      addedContainer.innerHTML = addedNodes.length > 0 ? addedNodes.map(n => `
        <div class="diff-item-row">
          <div>
            <span class="diff-tag-added">[+] ADDED</span>
            <strong>${escapeHtml(n.name || n.id)}</strong>
            <span class="node-badge badge-${n.type || 'Dataset'}" style="margin-left: 8px;">${n.type || 'Dataset'}</span>
          </div>
          <span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(n.description || n.id)}</span>
        </div>
      `).join('') : `<div style="font-size: 12px; color: var(--text-muted); text-align: center; padding: 20px;">No assets added between selected timestamps.</div>`;
    }

    const removedContainer = getEl('diff-tab-removed');
    if (removedContainer) {
      removedContainer.innerHTML = removedNodes.length > 0 ? removedNodes.map(n => `
        <div class="diff-item-row">
          <div>
            <span class="diff-tag-removed">[-] REMOVED</span>
            <strong>${escapeHtml(n.name || n.id)}</strong>
            <span class="node-badge badge-${n.type || 'Dataset'}" style="margin-left: 8px;">${n.type || 'Dataset'}</span>
          </div>
          <span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(n.description || n.id)}</span>
        </div>
      `).join('') : `<div style="font-size: 12px; color: var(--text-muted); text-align: center; padding: 20px;">No assets removed between selected timestamps.</div>`;
    }

    const modifiedContainer = getEl('diff-tab-modified');
    if (modifiedContainer) {
      modifiedContainer.innerHTML = modifiedNodes.length > 0 ? modifiedNodes.map(m => `
        <div class="diff-item-row" style="flex-direction: column; align-items: flex-start; gap: 4px;">
          <div>
            <span class="diff-tag-modified">[Δ] MODIFIED</span>
            <strong>${escapeHtml(m.id)}</strong>
          </div>
          <div style="font-size: 11px; color: var(--text-secondary); width: 100%;">
            <span style="color: var(--accent-rose);">Before:</span> ${escapeHtml(JSON.stringify(m.before))}
            <br>
            <span style="color: var(--accent-emerald);">After:</span> ${escapeHtml(JSON.stringify(m.after))}
          </div>
        </div>
      `).join('') : `<div style="font-size: 12px; color: var(--text-muted); text-align: center; padding: 20px;">No schema properties modified.</div>`;
    }

    const edgesContainer = getEl('diff-tab-edges');
    if (edgesContainer) {
      const allEdges = [
        ...addedEdges.map(e => ({ mode: 'added', ...e })),
        ...removedEdges.map(e => ({ mode: 'removed', ...e }))
      ];
      edgesContainer.innerHTML = allEdges.length > 0 ? allEdges.map(e => `
        <div class="diff-item-row">
          <div>
            <span class="${e.mode === 'added' ? 'diff-tag-added' : 'diff-tag-removed'}">[${e.mode === 'added' ? '+' : '-'}] ${e.mode.toUpperCase()} LINEAGE</span>
            <code>${escapeHtml(e.source_id)}</code> ➔ <code>${escapeHtml(e.target_id)}</code>
          </div>
          <span style="font-size: 11px; color: var(--text-muted);">${e.type || 'Edge'}</span>
        </div>
      `).join('') : `<div style="font-size: 12px; color: var(--text-muted); text-align: center; padding: 20px;">No lineage edges altered.</div>`;
    }

    const promptEl = getEl('diff-prompt-content');
    if (promptEl) promptEl.innerText = data.synthesized_prompt || 'No prompt generated.';

    if (typeof onApplyDiffVisualsCallback === 'function') {
      onApplyDiffVisualsCallback(diff);
    }
  } catch (err) {
    alert(`Error executing time diff: ${err.message}`);
  }
}

export function switchDiffTab(tabName) {
  const tabs = ['added', 'removed', 'modified', 'edges', 'prompt'];
  tabs.forEach(t => {
    const btn = getEl(`tab-btn-${t}`);
    const content = getEl(`diff-tab-${t}`);
    if (t === tabName) {
      if (btn) btn.classList.add('active');
      if (content) content.style.display = 'flex';
    } else {
      if (btn) btn.classList.remove('active');
      if (content) content.style.display = 'none';
    }
  });
}

export function sendDiffToAiAssistant() {
  if (!lastDiffResult || !lastDiffResult.synthesized_prompt) return;
  closeTimeDiffModal();
  if (typeof onOpenChatWithPromptCallback === 'function') {
    onOpenChatWithPromptCallback(`Analyze historical schema drift and lineage changes:\n\n${lastDiffResult.synthesized_prompt}`);
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    loadTimeline,
    onTimelineSliderChange,
    resetTimelineLive,
    openTimeDiffModal,
    closeTimeDiffModal,
    populateDiffDropdowns,
    executeTimeDiff,
    switchDiffTab,
    sendDiffToAiAssistant,
    getCurrentAsOfTimestamp,
    setCurrentAsOfTimestamp,
    setTimelineCallbacks
  };
}
