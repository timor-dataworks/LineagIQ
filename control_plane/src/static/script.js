/**
 * LineagIQ Control Plane - Main Application Entry Point
 * Orchestrates modules: api.js, graph.js, chat.js, timeline.js, utils.js
 */

import {
  getEl,
  getVal,
  escapeHtml,
  parseNodeProperties,
  showToast
} from './utils.js';

import {
  fetchGraph,
  fetchTimeline,
  searchDiscovery,
  fetchBlastRadius,
  fetchRootCause,
  sendChat,
  fetchTimeDiff
} from './api.js';

import {
  typeColors,
  buildColumnToDatasetMap,
  computeDagNodeLevels,
  formatGraphNodes,
  formatGraphEdges,
  computeDeterministicPositions,
  renderNetwork,
  getViewMode,
  filterGraph,
  handleSearchInput,
  loadGraph,
  fitGraphView,
  toggleLayout,
  displayNodeDetails,
  resetSidebar,
  highlightConnected,
  resetGraphHighlight,
  triggerBlastRadius,
  triggerRootCause,
  applyGraphDiffVisuals,
  getSelectedNodeId,
  setSelectedNodeId
} from './graph.js';

import {
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
} from './chat.js';

import {
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
} from './timeline.js';

// Connect cross-module callbacks
setTimelineCallbacks({
  reloadGraph: (refreshTimeline) => loadGraph(refreshTimeline),
  applyDiffVisuals: (diff) => applyGraphDiffVisuals(diff),
  openChatWithPrompt: (prompt) => {
    const drawer = getEl('chat-drawer');
    if (drawer) drawer.style.display = 'flex';
    const inputEl = getEl('chat-input');
    if (inputEl) inputEl.value = prompt;
    sendChatMessage();
  },
  getSelectedNodeId: () => getSelectedNodeId()
});

setHighlightTargetNodeCallback((targetNodeId) => {
  setSelectedNodeId(targetNodeId);
  highlightConnected(targetNodeId);
});

function closeAllDrawers() {
  resetSidebar();
  const drawer = getEl('chat-drawer');
  if (drawer) drawer.style.display = 'none';
  const backdrop = getEl('drawer-backdrop');
  if (backdrop) backdrop.style.display = 'none';
}

// Bind all public event handlers to global window object
// so inline HTML attributes (onclick, onchange, oninput) continue working flawlessly
if (typeof window !== 'undefined') {
  window.filterGraph = filterGraph;
  window.getViewMode = getViewMode;
  window.handleSearchInput = handleSearchInput;
  window.fitGraphView = fitGraphView;
  window.toggleLayout = toggleLayout;
  window.displayNodeDetails = displayNodeDetails;
  window.resetSidebar = resetSidebar;
  window.highlightConnected = highlightConnected;
  window.resetGraphHighlight = resetGraphHighlight;
  window.triggerBlastRadius = triggerBlastRadius;
  window.triggerRootCause = triggerRootCause;
  window.updateChatDrawerPosition = updateChatDrawerPosition;
  window.toggleChatDockMode = toggleChatDockMode;
  window.toggleChatDrawer = toggleChatDrawer;
  window.toggleChatSettings = toggleChatSettings;
  window.setOllamaConfig = setOllamaConfig;
  window.setOpenAiConfig = setOpenAiConfig;
  window.saveLlmSettings = saveLlmSettings;
  window.loadLlmSettings = loadLlmSettings;
  window.applySuggestedPrompt = applySuggestedPrompt;
  window.sendChatMessage = sendChatMessage;
  window.onTimelineSliderChange = onTimelineSliderChange;
  window.resetTimelineLive = resetTimelineLive;
  window.openTimeDiffModal = openTimeDiffModal;
  window.closeTimeDiffModal = closeTimeDiffModal;
  window.executeTimeDiff = executeTimeDiff;
  window.switchDiffTab = switchDiffTab;
  window.sendDiffToAiAssistant = sendDiffToAiAssistant;
  window.closeAllDrawers = closeAllDrawers;
  window.showToast = showToast;

  window.addEventListener('DOMContentLoaded', async () => {
    loadLlmSettings();
    loadGraph();
  });
  window.addEventListener('resize', updateChatDrawerPosition);
}

// Export for Node.js test suite compatibility
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    getEl,
    getVal,
    escapeHtml,
    parseNodeProperties,
    showToast,
    typeColors,
    buildColumnToDatasetMap,
    computeDeterministicPositions,
    computeDagNodeLevels,
    getViewMode,
    filterGraph,
    displayNodeDetails,
    resetSidebar,
    switchDiffTab,
    onTimelineSliderChange,
    resetTimelineLive,
    updateChatDrawerPosition,
    toggleChatDockMode,
    toggleChatDrawer,
    saveLlmSettings,
    loadLlmSettings,
    setOllamaConfig,
    setOpenAiConfig,
    applySuggestedPrompt,
    closeAllDrawers
  };
}

export {
  getEl,
  getVal,
  escapeHtml,
  parseNodeProperties,
  showToast,
  fetchGraph,
  fetchTimeline,
  searchDiscovery,
  fetchBlastRadius,
  fetchRootCause,
  sendChat,
  fetchTimeDiff,
  typeColors,
  buildColumnToDatasetMap,
  computeDagNodeLevels,
  formatGraphNodes,
  formatGraphEdges,
  computeDeterministicPositions,
  renderNetwork,
  getViewMode,
  filterGraph,
  handleSearchInput,
  loadGraph,
  fitGraphView,
  toggleLayout,
  displayNodeDetails,
  resetSidebar,
  highlightConnected,
  resetGraphHighlight,
  triggerBlastRadius,
  triggerRootCause,
  applyGraphDiffVisuals,
  getSelectedNodeId,
  setSelectedNodeId,
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
  closeAllDrawers
};
