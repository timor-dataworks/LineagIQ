let network = null;
let nodesDataSet = null;
let edgesDataSet = null;
let rawNodes = [];
let rawEdges = [];
let selectedNodeId = null;
let searchDebounceTimer = null;
let vectorMatchedIds = null;
let availableTimestamps = [];
let currentAsOfTimestamp = null;
let lastDiffResult = null;

const typeColors = {
  'Dataset': { background: '#0284c7', border: 'transparent', highlight: '#06b6d4' },
  'Column': { background: '#7c3aed', border: 'transparent', highlight: '#a855f7' },
  'Pipeline': { background: '#d97706', border: 'transparent', highlight: '#f59e0b' },
  'User': { background: '#059669', border: 'transparent', highlight: '#10b981' },
  'BusinessTerm': { background: '#e11d48', border: 'transparent', highlight: '#f43f5e' }
};

async function loadTimeline() {
  const tenantId = document.getElementById('tenant-input').value.trim() || 'demo_tenant';
  const dataPath = document.getElementById('data-path-input').value.trim();
  let url = `/api/v1/tenants/${tenantId}/timeline`;
  if (dataPath) url += `?data_path=${encodeURIComponent(dataPath)}`;

  try {
    const response = await fetch(url);
    if (!response.ok) return;
    const data = await response.json();
    availableTimestamps = data.timestamps || [];

    const panel = document.getElementById('timeline-panel');
    const slider = document.getElementById('timeline-slider');

    if (availableTimestamps.length > 1) {
      panel.style.display = 'flex';
      slider.max = availableTimestamps.length - 1;
      if (currentAsOfTimestamp === null) {
        slider.value = availableTimestamps.length - 1;
        document.getElementById('timeline-label').innerText = 'LIVE (Latest)';
      }
    } else {
      panel.style.display = 'none';
    }
  } catch (err) {
    console.warn("Timeline fetch error:", err);
  }
}

function onTimelineSliderChange(val) {
  const idx = parseInt(val, 10);
  if (idx === availableTimestamps.length - 1) {
    currentAsOfTimestamp = null;
    document.getElementById('timeline-label').innerText = 'LIVE (Latest)';
  } else if (idx < availableTimestamps.length) {
    const item = availableTimestamps[idx];
    currentAsOfTimestamp = item.timestamp;
    document.getElementById('timeline-label').innerHTML = `v${item.version} <span style="color: var(--accent-cyan);">${item.timestamp}</span>`;
  }
  loadGraph(false);
}

function resetTimelineLive() {
  const slider = document.getElementById('timeline-slider');
  slider.value = availableTimestamps.length > 0 ? availableTimestamps.length - 1 : 0;
  currentAsOfTimestamp = null;
  document.getElementById('timeline-label').innerText = 'LIVE (Latest)';
  loadGraph(false);
}

async function loadGraph(refreshTimeline = true) {
  const tenantId = document.getElementById('tenant-input').value.trim() || 'demo_tenant';
  const dataPath = document.getElementById('data-path-input').value.trim();

  let url = `/api/v1/tenants/${tenantId}/graph`;
  const params = [];
  if (dataPath) params.push(`data_path=${encodeURIComponent(dataPath)}`);
  if (currentAsOfTimestamp) params.push(`as_of=${encodeURIComponent(currentAsOfTimestamp)}`);
  if (params.length > 0) url += `?${params.join('&')}`;

  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Failed to fetch knowledge graph data.");
    const data = await response.json();

    rawNodes = data.nodes || [];
    rawEdges = data.edges || [];

    filterGraph();
    if (refreshTimeline) loadTimeline();
  } catch (err) {
    alert(`Error loading graph: ${err.message}`);
  }
}

function handleSearchInput() {
  const searchTerm = document.getElementById('search-input').value.trim();
  if (!searchTerm) {
    vectorMatchedIds = null;
    filterGraph();
    return;
  }

  if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(async () => {
    await performVectorSearch(searchTerm);
  }, 300);
}

async function performVectorSearch(queryText) {
  const tenantId = document.getElementById('tenant-input').value.trim() || 'demo_tenant';
  const dataPath = document.getElementById('data-path-input').value.trim();

  try {
    const response = await fetch(`/api/v1/tenants/${tenantId}/discovery`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: queryText,
        top_k: 10,
        data_path: dataPath,
        as_of: currentAsOfTimestamp || undefined,
      })
    });
    if (!response.ok) throw new Error("Vector search HTTP error");
    const data = await response.json();
    
    if (data.matched_nodes && data.matched_nodes.length > 0) {
      vectorMatchedIds = new Set(data.matched_nodes.map(n => n.id));
    } else {
      vectorMatchedIds = new Set();
    }
  } catch (err) {
    console.warn("Vector search fallback to local filter:", err);
    vectorMatchedIds = null;
  }

  filterGraph();
}

function filterGraph() {
  const viewMode = document.getElementById('view-mode').value;
  const searchTerm = document.getElementById('search-input').value.toLowerCase().trim();

  document.getElementById('legend-column').style.display = (viewMode === 'all') ? 'flex' : 'none';

  let visibleNodes = [...rawNodes];

  if (viewMode === 'high_level') {
    visibleNodes = visibleNodes.filter(n => n.type !== 'Column');
  }

  if (searchTerm) {
    if (vectorMatchedIds !== null && vectorMatchedIds.size > 0) {
      visibleNodes = visibleNodes.filter(n => vectorMatchedIds.has(n.id));
    } else if (vectorMatchedIds !== null && vectorMatchedIds.size === 0) {
      visibleNodes = [];
    } else {
      visibleNodes = visibleNodes.filter(n =>
        (n.name && n.name.toLowerCase().includes(searchTerm)) ||
        (n.id && n.id.toLowerCase().includes(searchTerm)) ||
        (n.type && n.type.toLowerCase().includes(searchTerm))
      );
    }
  }

  const visibleIds = new Set(visibleNodes.map(n => n.id));
  let visibleEdges = rawEdges.filter(e => visibleIds.has(e.source_id) && visibleIds.has(e.target_id));

  if (viewMode === 'high_level') {
    visibleEdges = visibleEdges.filter(e => e.type !== 'BELONGS_TO');
  }

  // Update Header Stats
  document.getElementById('stat-node-count').innerText = visibleNodes.length;
  document.getElementById('stat-edge-count').innerText = visibleEdges.length;

  renderNetwork(visibleNodes, visibleEdges);
}

function renderNetwork(nodesData, edgesData) {
  const isHierarchical = (document.getElementById('layout-mode').value === 'hierarchical');

  const formattedNodes = nodesData.map(n => {
    const isColumn = (n.type === 'Column');
    const color = typeColors[n.type] || { background: '#334155', border: 'transparent' };

    if (isColumn) {
      return {
        id: n.id,
        label: n.name || n.id,
        shape: 'box',
        margin: 6,
        borderWidth: 1,
        borderWidthSelected: 2,
        color: {
          background: '#4c1d95',
          border: '#7c3aed',
          highlight: { background: '#6d28d9', border: '#c084fc' },
          hover: { background: '#5b21b6', border: '#a855f7' }
        },
        font: { color: '#f3e8ff', size: 11, face: 'Inter', weight: '500' },
        shapeProperties: { borderRadius: 4 },
        rawNode: n
      };
    }

    const shape = n.type === 'Dataset' ? 'box' : (n.type === 'Pipeline' ? 'ellipse' : 'dot');
    return {
      id: n.id,
      label: n.name || n.id,
      shape: shape,
      size: n.type === 'Dataset' ? 22 : (n.type === 'Pipeline' ? 18 : 12),
      margin: 12,
      borderWidth: n.type === 'Dataset' ? 1 : 0,
      borderWidthSelected: 2,
      color: {
        background: color.background,
        border: color.border || 'transparent',
        highlight: { background: color.highlight, border: '#ffffff' },
        hover: { background: color.highlight, border: 'transparent' }
      },
      font: { color: '#ffffff', size: 13, face: 'Inter', weight: '600' },
      shapeProperties: { borderRadius: 6 },
      rawNode: n
    };
  });

  const formattedEdges = edgesData.map(e => {
    const isBelongsTo = (e.type === 'BELONGS_TO');
    return {
      from: e.source_id,
      to: e.target_id,
      label: isBelongsTo ? '' : e.type,
      arrows: isBelongsTo ? { to: { enabled: false } } : { to: { enabled: true, scaleFactor: 0.8 } },
      dashes: isBelongsTo ? [3, 4] : false,
      width: isBelongsTo ? 1 : 2,
      color: isBelongsTo
        ? { color: 'rgba(168, 85, 247, 0.4)', highlight: '#c084fc' }
        : { color: 'rgba(255, 255, 255, 0.45)', highlight: '#06b6d4' },
      font: {
        color: '#ffffff',
        size: 10,
        face: 'Inter',
        align: 'middle',
        strokeWidth: 0,
        background: 'rgba(15, 23, 42, 0.9)'
      },
      smooth: isHierarchical ? { type: 'cubicBezier', forceDirection: 'horizontal' } : { type: 'continuous' }
    };
  });

  nodesDataSet = new vis.DataSet(formattedNodes);
  edgesDataSet = new vis.DataSet(formattedEdges);

  const container = document.getElementById('network-canvas');
  const data = { nodes: nodesDataSet, edges: edgesDataSet };

  const options = {
    nodes: {
      borderWidth: 0,
      shadow: false
    },
    edges: {
      width: 2,
      shadow: false
    },
    layout: {
      hierarchical: {
        enabled: isHierarchical,
        direction: 'LR',
        sortMethod: 'directed',
        nodeSpacing: 180,
        levelSeparation: 240,
        treeSpacing: 200,
        blockShifting: true,
        edgeMinimization: true,
        parentCentralization: true
      }
    },
    physics: {
      enabled: !isHierarchical,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -40,
        centralGravity: 0.01,
        springLength: 100,
        springConstant: 0.08
      },
      stabilization: { iterations: 100 }
    },
    interaction: { hover: true, tooltipDelay: 200 }
  };

  if (network) network.destroy();
  network = new vis.Network(container, data, options);

  // Trigger automatic viewport fit so all nodes (including columns) are immediately framed and visible
  setTimeout(() => {
    if (network) network.fit({ animation: false });
  }, 100);

  network.once("stabilizationIterationsDone", function () {
    if (network) network.fit({ animation: { duration: 400 } });
  });

  network.on("selectNode", function (params) {
    if (params.nodes.length > 0) {
      selectedNodeId = params.nodes[0];
      const nodeObj = nodesData.find(n => n.id === selectedNodeId);
      displayNodeDetails(nodeObj);
      highlightConnected(selectedNodeId);
    }
  });

  network.on("deselectNode", function () {
    selectedNodeId = null;
    resetSidebar();
    resetGraphHighlight();
  });
}

function fitGraphView() {
  if (network) {
    network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
  }
}

function toggleLayout() {
  filterGraph();
}

function displayNodeDetails(node) {
  if (!node) return;
  document.getElementById('inspector-empty').style.display = 'none';
  const content = document.getElementById('inspector-content');
  content.style.display = 'flex';

  document.getElementById('panel-node-name').innerText = node.name || node.id;
  document.getElementById('panel-node-id').innerText = node.id;
  document.getElementById('panel-node-desc').innerText = node.description || 'No detailed description specified.';
  let propsObj = {};
  if (typeof node.properties === 'string') {
    try {
      propsObj = JSON.parse(node.properties);
    } catch (e) {
      propsObj = { raw: node.properties };
    }
  } else if (typeof node.properties === 'object' && node.properties !== null) {
    propsObj = node.properties;
  }
  document.getElementById('panel-node-props').innerText = JSON.stringify(propsObj, null, 2);

  const badge = document.getElementById('panel-node-type');
  badge.innerText = node.type || 'Node';
  badge.className = `node-badge badge-${node.type || 'Dataset'}`;

  document.getElementById('blast-btn').style.display = 'block';
  document.getElementById('root-cause-btn').style.display = 'block';
}

function highlightConnected(nodeId) {
  const connectedNodes = new Set(network.getConnectedNodes(nodeId));
  connectedNodes.add(nodeId);

  const allNodes = nodesDataSet.get();
  const updatedNodes = allNodes.map(n => {
    const isConnected = connectedNodes.has(n.id);
    return {
      id: n.id,
      opacity: isConnected ? 1.0 : 0.15
    };
  });
  nodesDataSet.update(updatedNodes);
}

function resetSidebar() {
  document.getElementById('inspector-content').style.display = 'none';
  document.getElementById('inspector-empty').style.display = 'flex';
  document.getElementById('blast-btn').style.display = 'none';
  document.getElementById('root-cause-btn').style.display = 'none';
}

async function triggerBlastRadius() {
  if (!selectedNodeId) return;
  const tenantId = document.getElementById('tenant-input').value.trim() || 'demo_tenant';
  const dataPath = document.getElementById('data-path-input').value.trim();

  try {
    const response = await fetch(`/api/v1/tenants/${tenantId}/blast-radius`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: selectedNodeId, max_depth: 5, data_path: dataPath })
    });
    const result = await response.json();

    const impactedIds = new Set((result.impacted_nodes || []).map(n => n.id));

    const currentNodes = nodesDataSet.get();
    const updatedNodes = currentNodes.map(n => {
      const isImpacted = impactedIds.has(n.id);
      const color = isImpacted
        ? { background: '#b91c1c', border: '#ef4444', highlight: { background: '#dc2626', border: '#ef4444' }, hover: { background: '#dc2626', border: '#ef4444' } }
        : { background: '#1e293b', border: 'transparent' };
      return {
        id: n.id,
        color: color,
        opacity: isImpacted ? 1.0 : 0.25
      };
    });

    nodesDataSet.update(updatedNodes);
    alert(`Blast Radius Calculation Complete!\n${result.impacted_nodes_count} downstream assets impacted.`);
  } catch (err) {
    alert(`Error calculating blast radius: ${err.message}`);
  }
}

async function triggerRootCause() {
  if (!selectedNodeId) return;
  const tenantId = document.getElementById('tenant-input').value.trim() || 'demo_tenant';
  const dataPath = document.getElementById('data-path-input').value.trim();

  try {
    const response = await fetch(`/api/v1/tenants/${tenantId}/root-cause`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: selectedNodeId, max_depth: 5, data_path: dataPath })
    });
    const result = await response.json();

    const upstreamIds = new Set((result.upstream_nodes || []).map(n => n.id));

    const currentNodes = nodesDataSet.get();
    const updatedNodes = currentNodes.map(n => {
      const isUpstream = upstreamIds.has(n.id);
      const color = isUpstream
        ? { background: '#d97706', border: '#f59e0b', highlight: { background: '#b45309', border: '#f59e0b' }, hover: { background: '#b45309', border: '#f59e0b' } }
        : { background: '#1e293b', border: 'transparent' };
      return {
        id: n.id,
        color: color,
        opacity: isUpstream ? 1.0 : 0.25
      };
    });

    nodesDataSet.update(updatedNodes);
    alert(`Upstream Root Cause Calculation Complete!\n${result.upstream_nodes_count} upstream assets & dependencies identified.`);
  } catch (err) {
    alert(`Error calculating upstream root cause: ${err.message}`);
  }
}

function resetGraphHighlight() {
  filterGraph();
  resetSidebar();
}

function toggleChatDrawer() {
  const drawer = document.getElementById('chat-drawer');
  drawer.style.display = (drawer.style.display === 'none' || !drawer.style.display) ? 'flex' : 'none';
}

function toggleChatSettings() {
  const panel = document.getElementById('chat-settings');
  panel.style.display = (panel.style.display === 'none' || !panel.style.display) ? 'flex' : 'none';
}

function saveLlmSettings() {
  const apiKey = document.getElementById('cfg-api-key').value;
  const baseUrl = document.getElementById('cfg-base-url').value;
  const model = document.getElementById('cfg-model').value;
  localStorage.setItem('lineagiq_api_key', apiKey);
  localStorage.setItem('lineagiq_base_url', baseUrl);
  localStorage.setItem('lineagiq_model', model);
}

function loadLlmSettings() {
  const apiKey = localStorage.getItem('lineagiq_api_key') || '';
  const baseUrl = localStorage.getItem('lineagiq_base_url') || '';
  const model = localStorage.getItem('lineagiq_model') || '';
  if (document.getElementById('cfg-api-key')) document.getElementById('cfg-api-key').value = apiKey;
  if (document.getElementById('cfg-base-url')) document.getElementById('cfg-base-url').value = baseUrl;
  if (document.getElementById('cfg-model')) document.getElementById('cfg-model').value = model;
}

function applySuggestedPrompt(promptText) {
  document.getElementById('chat-input').value = promptText;
  sendChatMessage();
}

async function sendChatMessage() {
  const inputEl = document.getElementById('chat-input');
  const message = inputEl.value.trim();
  if (!message) return;

  const tenantId = document.getElementById('tenant-input').value.trim() || 'demo_tenant';
  const dataPath = document.getElementById('data-path-input').value.trim();

  const apiKey = document.getElementById('cfg-api-key').value.trim() || undefined;
  const baseUrl = document.getElementById('cfg-base-url').value.trim() || undefined;
  const model = document.getElementById('cfg-model').value.trim() || undefined;

  const messagesContainer = document.getElementById('chat-messages');

  // Append user bubble
  const userMsgDiv = document.createElement('div');
  userMsgDiv.className = 'chat-msg chat-msg-user';
  userMsgDiv.innerHTML = `<div class="msg-bubble">${escapeHtml(message)}</div>`;
  messagesContainer.appendChild(userMsgDiv);

  inputEl.value = '';
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  // Append loading AI bubble
  const aiLoadingDiv = document.createElement('div');
  aiLoadingDiv.className = 'chat-msg chat-msg-ai';
  aiLoadingDiv.innerHTML = `<div class="msg-bubble"><em>Analyzing Knowledge Graph...</em></div>`;
  messagesContainer.appendChild(aiLoadingDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  try {
    const response = await fetch(`/api/v1/tenants/${tenantId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message,
        data_path: dataPath,
        openai_api_key: apiKey,
        openai_base_url: baseUrl,
        openai_model: model
      })
    });
    
    if (!response.ok) throw new Error("API request failed");
    const data = await response.json();

    // Update AI response
    aiLoadingDiv.querySelector('.msg-bubble').innerHTML = formatMarkdown(data.reply);

    if (data.target_node_id && typeof highlightConnected === 'function') {
      selectedNodeId = data.target_node_id;
      highlightConnected(data.target_node_id);
    }
  } catch (err) {
    aiLoadingDiv.querySelector('.msg-bubble').innerHTML = `<span style="color: var(--accent-rose);">Error: ${escapeHtml(err.message)}</span>`;
  }

  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function formatMarkdown(text) {
  if (!text) return "";
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/`([^`]+)`/g, "<code style='background: rgba(2, 6, 23, 0.6); color: #38bdf8; padding: 2px 6px; border-radius: 4px;'>$1</code>");
  html = html.replace(/\n/g, "<br>");
  return html;
}

function openTimeDiffModal() {
  const modal = document.getElementById('time-diff-modal');
  modal.style.display = 'flex';
  populateDiffDropdowns();
}

function closeTimeDiffModal() {
  document.getElementById('time-diff-modal').style.display = 'none';
}

function populateDiffDropdowns() {
  const sel1 = document.getElementById('diff-t1-select');
  const sel2 = document.getElementById('diff-t2-select');
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

  if (selectedNodeId && document.getElementById('diff-node-input')) {
    document.getElementById('diff-node-input').value = selectedNodeId;
  }
}

async function executeTimeDiff() {
  const t1 = document.getElementById('diff-t1-select').value;
  const t2 = document.getElementById('diff-t2-select').value;
  const nodeId = document.getElementById('diff-node-input').value.trim();
  const tenantId = document.getElementById('tenant-input').value.trim() || 'demo_tenant';
  const dataPath = document.getElementById('data-path-input').value.trim();

  if (!t1 || !t2) {
    alert("Please select baseline (T1) and compare (T2) timestamps.");
    return;
  }

  try {
    const response = await fetch(`/api/v1/tenants/${tenantId}/time-travel/diff`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_id: nodeId,
        timestamp_t1: t1,
        timestamp_t2: t2,
        data_path: dataPath
      })
    });

    if (!response.ok) throw new Error("Time Travel Diff request failed");
    const data = await response.json();
    lastDiffResult = data;

    const diff = data.diff || {};
    const addedNodes = diff.added_nodes || [];
    const removedNodes = diff.removed_nodes || [];
    const modifiedNodes = diff.modified_nodes || [];
    const addedEdges = diff.added_edges || [];
    const removedEdges = diff.removed_edges || [];

    document.getElementById('diff-count-added').innerText = addedNodes.length;
    document.getElementById('diff-count-removed').innerText = removedNodes.length;
    document.getElementById('diff-count-modified').innerText = modifiedNodes.length;
    document.getElementById('diff-count-edges').innerText = addedEdges.length + removedEdges.length;

    document.getElementById('badge-tab-added').innerText = addedNodes.length;
    document.getElementById('badge-tab-removed').innerText = removedNodes.length;
    document.getElementById('badge-tab-modified').innerText = modifiedNodes.length;
    document.getElementById('badge-tab-edges').innerText = addedEdges.length + removedEdges.length;

    // Render Added
    const addedContainer = document.getElementById('diff-tab-added');
    if (addedNodes.length > 0) {
      addedContainer.innerHTML = addedNodes.map(n => `
        <div class="diff-item-row">
          <div>
            <span class="diff-tag-added">[+] ADDED</span>
            <strong>${escapeHtml(n.name || n.id)}</strong>
            <span class="node-badge badge-${n.type || 'Dataset'}" style="margin-left: 8px;">${n.type || 'Dataset'}</span>
          </div>
          <span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(n.description || n.id)}</span>
        </div>
      `).join('');
    } else {
      addedContainer.innerHTML = `<div style="font-size: 12px; color: var(--text-muted); text-align: center; padding: 20px;">No assets added between selected timestamps.</div>`;
    }

    // Render Removed
    const removedContainer = document.getElementById('diff-tab-removed');
    if (removedNodes.length > 0) {
      removedContainer.innerHTML = removedNodes.map(n => `
        <div class="diff-item-row">
          <div>
            <span class="diff-tag-removed">[-] REMOVED</span>
            <strong>${escapeHtml(n.name || n.id)}</strong>
            <span class="node-badge badge-${n.type || 'Dataset'}" style="margin-left: 8px;">${n.type || 'Dataset'}</span>
          </div>
          <span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(n.description || n.id)}</span>
        </div>
      `).join('');
    } else {
      removedContainer.innerHTML = `<div style="font-size: 12px; color: var(--text-muted); text-align: center; padding: 20px;">No assets removed between selected timestamps.</div>`;
    }

    // Render Modified
    const modifiedContainer = document.getElementById('diff-tab-modified');
    if (modifiedNodes.length > 0) {
      modifiedContainer.innerHTML = modifiedNodes.map(m => `
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
      `).join('');
    } else {
      modifiedContainer.innerHTML = `<div style="font-size: 12px; color: var(--text-muted); text-align: center; padding: 20px;">No schema properties modified.</div>`;
    }

    // Render Edges
    const edgesContainer = document.getElementById('diff-tab-edges');
    const allEdges = [
      ...addedEdges.map(e => ({ mode: 'added', ...e })),
      ...removedEdges.map(e => ({ mode: 'removed', ...e }))
    ];
    if (allEdges.length > 0) {
      edgesContainer.innerHTML = allEdges.map(e => `
        <div class="diff-item-row">
          <div>
            <span class="${e.mode === 'added' ? 'diff-tag-added' : 'diff-tag-removed'}">[${e.mode === 'added' ? '+' : '-'}] ${e.mode.toUpperCase()} LINEAGE</span>
            <code>${escapeHtml(e.source_id)}</code> ➔ <code>${escapeHtml(e.target_id)}</code>
          </div>
          <span style="font-size: 11px; color: var(--text-muted);">${e.type || 'Edge'}</span>
        </div>
      `).join('');
    } else {
      edgesContainer.innerHTML = `<div style="font-size: 12px; color: var(--text-muted); text-align: center; padding: 20px;">No lineage edges altered.</div>`;
    }

    // Synthesized Prompt
    document.getElementById('diff-prompt-content').innerText = data.synthesized_prompt || 'No prompt generated.';

    applyGraphDiffVisuals(diff);

  } catch (err) {
    alert(`Error executing time diff: ${err.message}`);
  }
}

function switchDiffTab(tabName) {
  const tabs = ['added', 'removed', 'modified', 'edges', 'prompt'];
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-btn-${t}`);
    const content = document.getElementById(`diff-tab-${t}`);
    if (t === tabName) {
      if (btn) btn.classList.add('active');
      if (content) content.style.display = 'flex';
    } else {
      if (btn) btn.classList.remove('active');
      if (content) content.style.display = 'none';
    }
  });
}

function applyGraphDiffVisuals(diff) {
  if (!nodesDataSet) return;

  const addedIds = new Set((diff.added_nodes || []).map(n => n.id));
  const removedIds = new Set((diff.removed_nodes || []).map(n => n.id));
  const modifiedIds = new Set((diff.modified_nodes || []).map(n => n.id));

  const allNodes = nodesDataSet.get();
  const updatedNodes = allNodes.map(n => {
    let color = { background: '#1e293b', border: 'transparent' };
    let opacity = 0.35;
    let label = n.label || n.id;

    if (addedIds.has(n.id)) {
      color = { background: '#059669', border: '#10b981', highlight: { background: '#10b981', border: '#34d399' } };
      opacity = 1.0;
      if (!label.startsWith('[+]')) label = `[+] ${label}`;
    } else if (removedIds.has(n.id)) {
      color = { background: '#b91c1c', border: '#ef4444', highlight: { background: '#f43f5e', border: '#f87171' } };
      opacity = 1.0;
      if (!label.startsWith('[-]')) label = `[-] ${label}`;
    } else if (modifiedIds.has(n.id)) {
      color = { background: '#d97706', border: '#f59e0b', highlight: { background: '#fbbf24', border: '#fef08a' } };
      opacity = 1.0;
      if (!label.startsWith('[Δ]')) label = `[Δ] ${label}`;
    }

    return {
      id: n.id,
      color: color,
      opacity: opacity,
      label: label
    };
  });

  nodesDataSet.update(updatedNodes);
}

function sendDiffToAiAssistant() {
  if (!lastDiffResult || !lastDiffResult.synthesized_prompt) return;
  closeTimeDiffModal();
  const drawer = document.getElementById('chat-drawer');
  drawer.style.display = 'flex';

  const inputEl = document.getElementById('chat-input');
  inputEl.value = `Analyze historical schema drift and lineage changes:\n\n${lastDiffResult.synthesized_prompt}`;
  sendChatMessage();
}

if (typeof window !== 'undefined') {
  window.addEventListener('DOMContentLoaded', () => {
    loadLlmSettings();
    loadGraph();
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    escapeHtml,
    formatMarkdown,
    switchDiffTab,
    typeColors,
    onTimelineSliderChange,
    resetTimelineLive,
    displayNodeDetails,
    resetSidebar,
    saveLlmSettings,
    loadLlmSettings,
    applySuggestedPrompt
  };
}
