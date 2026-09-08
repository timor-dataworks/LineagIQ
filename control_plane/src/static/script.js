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
  'ColumnCloud': { background: '#2e1065', border: '#7c3aed', highlight: '#c084fc' },
  'Pipeline': { background: '#d97706', border: 'transparent', highlight: '#f59e0b' },
  'User': { background: '#059669', border: 'transparent', highlight: '#10b981' },
  'BusinessTerm': { background: '#e11d48', border: 'transparent', highlight: '#f43f5e' }
};

const getEl = (id) => (typeof document !== 'undefined' ? document.getElementById(id) : null);
const getVal = (id, fallback = '') => {
  const el = getEl(id);
  return el ? el.value.trim() || fallback : fallback;
};

function parseNodeProperties(node) {
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

function buildColumnToDatasetMap(nodes, edges) {
  const map = {};
  (nodes || []).forEach(n => {
    if (n.type === 'Column') {
      const props = parseNodeProperties(n);
      let dsId = props.dataset_id;
      if (!dsId && n.id && n.id.includes('.')) {
        dsId = n.id.substring(0, n.id.lastIndexOf('.'));
      }
      if (dsId) map[n.id] = dsId;
    }
  });
  (edges || []).forEach(e => {
    if (e.type === 'BELONGS_TO' && e.source_id && e.target_id) {
      map[e.source_id] = e.target_id;
    }
  });
  return map;
}

async function loadTimeline() {
  const tenantId = getVal('tenant-input', 'demo_tenant');
  const dataPath = getVal('data-path-input');
  let url = `/api/v1/tenants/${tenantId}/timeline`;
  if (dataPath) url += `?data_path=${encodeURIComponent(dataPath)}`;

  try {
    const response = await fetch(url);
    if (!response.ok) return;
    const data = await response.json();
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

let timelineDebounceTimer = null;

function onTimelineSliderChange(val) {
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
    loadGraph(false);
  }, 200);
}

function resetTimelineLive() {
  const slider = getEl('timeline-slider');
  const label = getEl('timeline-label');
  const maxIdx = availableTimestamps.length > 0 ? availableTimestamps.length - 1 : 0;
  if (slider) slider.value = maxIdx;
  currentAsOfTimestamp = null;
  const lastItem = availableTimestamps[maxIdx];
  if (label) label.innerText = `LIVE (v${lastItem ? lastItem.version : 'Latest'})`;
  loadGraph(false);
}

async function loadGraph(refreshTimeline = true) {
  const tenantId = getVal('tenant-input', 'demo_tenant');
  const dataPath = getVal('data-path-input');

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
    console.error("Error loading graph:", err);
  }
}

function handleSearchInput() {
  const searchTerm = getVal('search-input');
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
  const tenantId = getVal('tenant-input', 'demo_tenant');
  const dataPath = getVal('data-path-input');

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
    vectorMatchedIds = new Set((data.matched_nodes || []).map(n => n.id));
  } catch (err) {
    console.warn("Vector search fallback to local filter:", err);
    vectorMatchedIds = null;
  }

  filterGraph();
}

function filterGraph() {
  const viewMode = getVal('view-mode', 'high_level');
  const searchTerm = getVal('search-input').toLowerCase();

  const legendCol = getEl('legend-column');
  if (legendCol) legendCol.style.display = (viewMode === 'all') ? 'flex' : 'none';

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

  const colToDatasetMap = buildColumnToDatasetMap(rawNodes, rawEdges);
  const visibleIds = new Set(visibleNodes.map(n => n.id));
  const edgeDedupe = new Set();
  const joinEdgesByPair = {};
  const nonJoinEdges = [];

  rawEdges.forEach(e => {
    if (viewMode === 'high_level' && e.type === 'BELONGS_TO') return;

    let srcId = e.source_id;
    let tgtId = e.target_id;

    if (viewMode === 'high_level') {
      if (colToDatasetMap[srcId]) srcId = colToDatasetMap[srcId];
      if (colToDatasetMap[tgtId]) tgtId = colToDatasetMap[tgtId];
    }

    if (srcId && tgtId && visibleIds.has(srcId) && visibleIds.has(tgtId) && srcId !== tgtId) {
      if (e.type === 'JOINS_WITH') {
        const pairKey = [srcId, tgtId].sort().join('--');
        const rawSrc = (e.source_id || '').toLowerCase();
        const rawTgt = (e.target_id || '').toLowerCase();

        // In dimensional data modeling, primary key dimension tables (.id) are upstream
        // of referencing foreign key fact tables (_id). Orient joins Left-to-Right (PK -> FK).
        let score = 0;
        if (rawSrc.endsWith('.id') && rawTgt.includes('_id')) {
          score = 2;
        } else if (rawSrc.includes('_id') && rawTgt.endsWith('.id')) {
          score = 1;
        }

        if (!joinEdgesByPair[pairKey] || score > joinEdgesByPair[pairKey].score) {
          joinEdgesByPair[pairKey] = {
            edge: { ...e, source_id: srcId, target_id: tgtId },
            score: score
          };
        }
      } else {
        const key = `${srcId}->${tgtId}:${e.type}`;
        if (!edgeDedupe.has(key)) {
          edgeDedupe.add(key);
          nonJoinEdges.push({
            ...e,
            source_id: srcId,
            target_id: tgtId
          });
        }
      }
    }
  });

  const visibleEdges = [...nonJoinEdges];
  Object.values(joinEdgesByPair).forEach(item => {
    visibleEdges.push(item.edge);
  });

  const nodeCountEl = getEl('stat-node-count');
  const edgeCountEl = getEl('stat-edge-count');
  if (nodeCountEl) nodeCountEl.innerText = visibleNodes.length;
  if (edgeCountEl) edgeCountEl.innerText = visibleEdges.length;

  renderNetwork(visibleNodes, visibleEdges);
}

function computeDagNodeLevels(nodes, edgesData) {
  const levels = {};
  const inDegree = {};
  const adj = {};

  const isBackbone = (n) => {
    const raw = n.rawNode || n;
    const type = raw.type || n.type;
    return (type === 'Dataset' || type === 'Pipeline');
  };

  const backboneNodes = nodes.filter(n => isBackbone(n));
  const backboneIds = new Set(backboneNodes.map(n => n.id));

  backboneIds.forEach(id => {
    inDegree[id] = 0;
    adj[id] = [];
  });

  edgesData.forEach(e => {
    const src = e.source_id || e.from;
    const tgt = e.target_id || e.to;
    if (e.type !== 'BELONGS_TO' && backboneIds.has(src) && backboneIds.has(tgt)) {
      if (src !== tgt) {
        adj[src].push(tgt);
        inDegree[tgt] = (inDegree[tgt] || 0) + 1;
      }
    }
  });

  const queue = [];
  backboneIds.forEach(id => {
    if (inDegree[id] === 0) {
      queue.push(id);
      levels[id] = 0;
    }
  });

  while (queue.length > 0) {
    const curr = queue.shift();
    const currLevel = levels[curr] || 0;

    (adj[curr] || []).forEach(neighbor => {
      levels[neighbor] = Math.max(levels[neighbor] || 0, currLevel + 1);
      inDegree[neighbor]--;
      if (inDegree[neighbor] === 0) {
        queue.push(neighbor);
      }
    });
  }

  backboneIds.forEach(id => {
    if (levels[id] === undefined) levels[id] = 0;
  });

  nodes.forEach(n => {
    const raw = n.rawNode || n;
    const type = raw.type || n.type;
    if (!isBackbone(n)) {
      if (type === 'ColumnCloud' || type === 'Column') {
        const props = parseNodeProperties(raw);
        let datasetId = props.dataset_id;
        if (!datasetId && n.id.includes('__column_cloud')) {
          datasetId = n.id.replace('__column_cloud', '');
        }
        levels[n.id] = (datasetId && levels[datasetId] !== undefined) ? levels[datasetId] : 0;
      } else if (type === 'User') {
        let maxParentLevel = 0;
        edgesData.forEach(e => {
          const src = e.source_id || e.from;
          const tgt = e.target_id || e.to;
          if (tgt === n.id && levels[src] !== undefined) {
            maxParentLevel = Math.max(maxParentLevel, levels[src]);
          }
        });
        levels[n.id] = maxParentLevel + 1;
      } else {
        levels[n.id] = 0;
      }
    }
  });

  return levels;
}

function formatGraphNodes(nodesData, edgesData) {
  const nonColumnNodes = nodesData.filter(n => n.type !== 'Column');
  const columnNodes = nodesData.filter(n => n.type === 'Column');

  const columnToParentMap = buildColumnToDatasetMap(nodesData, edgesData);
  const columnsByDataset = {};

  columnNodes.forEach(c => {
    const parentId = columnToParentMap[c.id];
    if (parentId) {
      if (!columnsByDataset[parentId]) columnsByDataset[parentId] = [];
      columnsByDataset[parentId].push(c);
    }
  });

  const formattedNodes = nonColumnNodes.map(n => {
    const color = typeColors[n.type] || { background: '#334155', border: 'transparent' };
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

  const columnCloudNodeMap = {};
  Object.keys(columnsByDataset).forEach(dsId => {
    const cols = columnsByDataset[dsId];
    const cloudId = `${dsId}__column_cloud`;
    columnCloudNodeMap[dsId] = cloudId;

    const colLines = cols.map(c => {
      const props = parseNodeProperties(c);
      const dataTypeStr = (props.data_type || props.type) ? ` (${props.data_type || props.type})` : '';
      return `• ${c.name || c.id}${dataTypeStr}`;
    });

    const label = `☁️ Columns (${cols.length})\n─────────────────\n${colLines.join('\n')}`;

    formattedNodes.push({
      id: cloudId,
      label: label,
      shape: 'box',
      margin: 10,
      borderWidth: 1,
      borderWidthSelected: 2,
      color: {
        background: '#2e1065',
        border: '#7c3aed',
        highlight: { background: '#4c1d95', border: '#c084fc' },
        hover: { background: '#3b0764', border: '#a855f7' }
      },
      font: { color: '#e9d5ff', size: 11, face: 'Inter', weight: '500', align: 'left' },
      shapeProperties: { borderRadius: 8 },
      rawNode: {
        id: cloudId,
        name: `Columns (${cols.length})`,
        type: 'ColumnCloud',
        description: `Column schema cloud for ${dsId}`,
        columns: cols,
        properties: { dataset_id: dsId, total_columns: cols.length }
      }
    });
  });

  return { formattedNodes, columnToParentMap, columnCloudNodeMap };
}

function formatGraphEdges(edgesData, columnToParentMap, columnCloudNodeMap, isHierarchical) {
  const formattedEdges = [];
  const processedCloudEdges = new Set();

  edgesData.forEach(e => {
    if (e.type === 'BELONGS_TO') {
      const parentDsId = columnToParentMap[e.source_id] || e.target_id;
      const cloudId = columnCloudNodeMap[parentDsId];
      if (cloudId && !processedCloudEdges.has(cloudId)) {
        processedCloudEdges.add(cloudId);
        formattedEdges.push({
          from: cloudId,
          to: parentDsId,
          label: '',
          arrows: { to: { enabled: false } },
          dashes: [3, 4],
          width: 1.5,
          color: { color: 'rgba(168, 85, 247, 0.65)', highlight: '#c084fc' }
        });
      }
    } else {
      let fromId = e.source_id;
      let toId = e.target_id;

      if (columnToParentMap[fromId] && columnCloudNodeMap[columnToParentMap[fromId]]) {
        fromId = columnCloudNodeMap[columnToParentMap[fromId]];
      }
      if (columnToParentMap[toId] && columnCloudNodeMap[columnToParentMap[toId]]) {
        toId = columnCloudNodeMap[columnToParentMap[toId]];
      }

      formattedEdges.push({
        from: fromId,
        to: toId,
        label: e.type,
        arrows: { to: { enabled: true, scaleFactor: 0.8 } },
        color: { color: 'rgba(255, 255, 255, 0.45)', highlight: '#06b6d4' },
        font: {
          color: '#e2e8f0',
          size: 10,
          face: 'Inter',
          align: 'horizontal',
          strokeWidth: 2,
          strokeColor: '#0f172a',
          background: 'rgba(15, 23, 42, 0.8)'
        },
        smooth: isHierarchical ? { type: 'cubicBezier', forceDirection: 'horizontal' } : { type: 'continuous' }
      });
    }
  });

  return formattedEdges;
}

function computeDeterministicPositions(formattedNodes, formattedEdges, isHierarchical) {
  const levels = computeDagNodeLevels(formattedNodes, formattedEdges);

  const nodesByLevel = {};
  formattedNodes.forEach(n => {
    const lvl = levels[n.id] !== undefined ? levels[n.id] : 0;
    n.level = lvl;
    if (!nodesByLevel[lvl]) nodesByLevel[lvl] = [];
    nodesByLevel[lvl].push(n);
  });

  if (!isHierarchical) return;

  const levelsSorted = Object.keys(nodesByLevel).map(Number).sort((a, b) => a - b);

  levelsSorted.forEach(lvl => {
    const allAtLvl = nodesByLevel[lvl];
    const backboneAtLvl = allAtLvl.filter(n => !n.id.endsWith('__column_cloud') && n.type !== 'ColumnCloud');
    const cloudAtLvl = allAtLvl.filter(n => n.id.endsWith('__column_cloud') || n.type === 'ColumnCloud');

    const count = backboneAtLvl.length;
    const baseSpacing = 280;
    const startY = -((count - 1) / 2) * baseSpacing;

    backboneAtLvl.forEach((n, idx) => {
      n.x = lvl * 360;
      n.y = startY + (idx * baseSpacing);

      const cloudNode = cloudAtLvl.find(c => c.id === `${n.id}__column_cloud`);
      if (cloudNode) {
        cloudNode.x = n.x;
        cloudNode.y = n.y + 130;
      }
    });

    const remainingSatellites = allAtLvl.filter(n => n.x === undefined);
    remainingSatellites.forEach((n, idx) => {
      n.x = lvl * 360;
      n.y = startY + ((count + idx) * baseSpacing);
    });
  });
}

function renderNetwork(nodesData, edgesData) {
  const isHierarchical = (getVal('layout-mode') === 'hierarchical');

  const { formattedNodes, columnToParentMap, columnCloudNodeMap } = formatGraphNodes(nodesData, edgesData);
  const formattedEdges = formatGraphEdges(edgesData, columnToParentMap, columnCloudNodeMap, isHierarchical);

  computeDeterministicPositions(formattedNodes, formattedEdges, isHierarchical);

  if (isHierarchical) {
    // Pure Vis.js native hierarchical LR layout:
    // Remove manual coordinate overrides so Vis.js DAG engine manages ranks and spacing natively
    formattedNodes.forEach(n => {
      delete n.x;
      delete n.y;
      delete n.level;
    });
  }

  if (network && nodesDataSet && edgesDataSet) {
    const prevPosition = network.getViewPosition();
    const prevScale = network.getScale();

    nodesDataSet.clear();
    nodesDataSet.add(formattedNodes);
    edgesDataSet.clear();
    edgesDataSet.add(formattedEdges);

    network.moveTo({ position: prevPosition, scale: prevScale, animation: false });
    return;
  }

  nodesDataSet = new vis.DataSet(formattedNodes);
  edgesDataSet = new vis.DataSet(formattedEdges);

  const container = getEl('network-canvas');
  const data = { nodes: nodesDataSet, edges: edgesDataSet };

  const options = {
    nodes: { borderWidth: 0, shadow: false },
    edges: {
      width: 2,
      shadow: false,
      smooth: isHierarchical ? { type: 'cubicBezier', forceDirection: 'horizontal' } : { type: 'continuous' }
    },
    layout: {
      hierarchical: {
        enabled: isHierarchical,
        direction: 'LR',
        sortMethod: 'directed',
        levelSeparation: 240,
        nodeSpacing: 100,
        treeSpacing: 45,
        blockShifting: true,
        edgeMinimization: true,
        parentCentralization: true
      }
    },
    physics: {
      enabled: true,
      solver: isHierarchical ? 'hierarchicalRepulsion' : 'forceAtlas2Based',
      hierarchicalRepulsion: {
        centralGravity: 0.0,
        springLength: 100,
        springConstant: 0.01,
        nodeDistance: 90,
        damping: 0.09
      },
      forceAtlas2Based: {
        gravitationalConstant: -40,
        centralGravity: 0.01,
        springLength: 100,
        springConstant: 0.08
      },
      stabilization: { iterations: 120 }
    },
    interaction: { hover: true, tooltipDelay: 200 }
  };

  if (network) network.destroy();
  network = new vis.Network(container, data, options);

  network.once("stabilizationIterationsDone", function () {
    if (network) network.fit({ animation: false });
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
  const sidebar = getEl('sidebar');
  if (sidebar) sidebar.style.display = 'flex';
  updateChatDrawerPosition();

  const emptyInspector = getEl('inspector-empty');
  const contentInspector = getEl('inspector-content');
  if (emptyInspector) emptyInspector.style.display = 'none';
  if (contentInspector) contentInspector.style.display = 'flex';

  const nameEl = getEl('panel-node-name');
  const idEl = getEl('panel-node-id');
  const descEl = getEl('panel-node-desc');
  const propsEl = getEl('panel-node-props');
  const badgeEl = getEl('panel-node-type');
  const blastBtn = getEl('blast-btn');
  const rootBtn = getEl('root-cause-btn');

  if (nameEl) nameEl.innerText = node.name || node.id;
  if (idEl) idEl.innerText = node.id;
  if (descEl) descEl.innerText = node.description || 'No detailed description specified.';

  const propsObj = parseNodeProperties(node);
  if (propsEl) propsEl.innerText = JSON.stringify(propsObj, null, 2);

  if (badgeEl) {
    badgeEl.innerText = node.type || 'Node';
    badgeEl.className = `node-badge badge-${node.type || 'Dataset'}`;
  }

  if (blastBtn) {
    blastBtn.style.display = 'block';
    blastBtn.innerText = '⚡ Compute Downstream Blast Radius';
    blastBtn.disabled = false;
  }
  if (rootBtn) {
    rootBtn.style.display = 'block';
    rootBtn.innerText = '🔍 Compute Upstream Root Cause';
    rootBtn.disabled = false;
  }
}

function highlightConnected(nodeId) {
  if (!network || !nodesDataSet) return;
  const connectedNodes = new Set(network.getConnectedNodes(nodeId));
  connectedNodes.add(nodeId);

  const allNodes = nodesDataSet.get();
  const updatedNodes = allNodes.map(n => ({
    id: n.id,
    opacity: connectedNodes.has(n.id) ? 1.0 : 0.15
  }));
  nodesDataSet.update(updatedNodes);
}

function resetSidebar() {
  const sidebar = getEl('sidebar');
  if (sidebar) sidebar.style.display = 'none';
  updateChatDrawerPosition();

  const contentInspector = getEl('inspector-content');
  const emptyInspector = getEl('inspector-empty');
  const blastBtn = getEl('blast-btn');
  const rootBtn = getEl('root-cause-btn');

  if (contentInspector) contentInspector.style.display = 'none';
  if (emptyInspector) emptyInspector.style.display = 'none';
  if (blastBtn) blastBtn.style.display = 'none';
  if (rootBtn) rootBtn.style.display = 'none';
  selectedNodeId = null;
}

async function triggerBlastRadius() {
  if (!selectedNodeId) return;
  const tenantId = getVal('tenant-input', 'demo_tenant');
  const dataPath = getVal('data-path-input');
  const blastBtn = getEl('blast-btn');

  try {
    if (blastBtn) {
      blastBtn.innerText = '⏳ Calculating Blast Radius...';
      blastBtn.disabled = true;
    }
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
      return {
        id: n.id,
        color: isImpacted
          ? { background: '#b91c1c', border: '#ef4444', highlight: { background: '#dc2626', border: '#ef4444' }, hover: { background: '#dc2626', border: '#ef4444' } }
          : { background: '#1e293b', border: 'transparent' },
        opacity: isImpacted ? 1.0 : 0.25
      };
    });

    nodesDataSet.update(updatedNodes);
    if (blastBtn) {
      blastBtn.innerText = `⚡ Downstream: ${result.impacted_nodes_count} assets impacted`;
      blastBtn.disabled = false;
    }
  } catch (err) {
    console.error("Error calculating blast radius:", err);
    if (blastBtn) {
      blastBtn.innerText = '⚠️ Calculation Failed';
      blastBtn.disabled = false;
    }
  }
}

async function triggerRootCause() {
  if (!selectedNodeId) return;
  const tenantId = getVal('tenant-input', 'demo_tenant');
  const dataPath = getVal('data-path-input');
  const rootBtn = getEl('root-cause-btn');

  try {
    if (rootBtn) {
      rootBtn.innerText = '⏳ Calculating Root Cause...';
      rootBtn.disabled = true;
    }
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
      return {
        id: n.id,
        color: isUpstream
          ? { background: '#d97706', border: '#f59e0b', highlight: { background: '#b45309', border: '#f59e0b' }, hover: { background: '#b45309', border: '#f59e0b' } }
          : { background: '#1e293b', border: 'transparent' },
        opacity: isUpstream ? 1.0 : 0.25
      };
    });

    nodesDataSet.update(updatedNodes);
    if (rootBtn) {
      rootBtn.innerText = `🔍 Upstream: ${result.upstream_nodes_count} dependencies found`;
      rootBtn.disabled = false;
    }
  } catch (err) {
    console.error("Error calculating upstream root cause:", err);
    if (rootBtn) {
      rootBtn.innerText = '⚠️ Calculation Failed';
      rootBtn.disabled = false;
    }
  }
}

function resetGraphHighlight() {
  filterGraph();
  resetSidebar();
}

let chatDockMode = 'dynamic'; // 'dynamic' | 'right' | 'left'

function updateChatDrawerPosition() {
  const drawer = getEl('chat-drawer');
  if (!drawer) return;

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

  // Dynamic mode: when Node Properties is opened, move slightly to left so it docks to Node Properties right side;
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

function toggleChatDockMode() {
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

function toggleChatDrawer() {
  const drawer = getEl('chat-drawer');
  if (!drawer) return;
  const willShow = (drawer.style.display === 'none' || !drawer.style.display);
  drawer.style.display = willShow ? 'flex' : 'none';
  if (willShow) {
    updateChatDrawerPosition();
  }
}

function toggleChatSettings() {
  const panel = getEl('chat-settings');
  if (panel) panel.style.display = (panel.style.display === 'none' || !panel.style.display) ? 'flex' : 'none';
}

function setOllamaConfig() {
  const urlEl = getEl('cfg-base-url');
  const modelEl = getEl('cfg-model');
  const keyEl = getEl('cfg-api-key');
  if (urlEl) urlEl.value = 'http://localhost:11434/v1';
  if (modelEl) modelEl.value = 'llama3';
  if (keyEl) keyEl.value = 'ollama';
  saveLlmSettings();
  showToast('Configured for local Ollama (http://localhost:11434/v1, model: llama3)');
}

function setOpenAiConfig() {
  const urlEl = getEl('cfg-base-url');
  const modelEl = getEl('cfg-model');
  const keyEl = getEl('cfg-api-key');
  if (urlEl) urlEl.value = '';
  if (modelEl) modelEl.value = '';
  if (keyEl) keyEl.value = '';
  saveLlmSettings();
  showToast('Reset to default OpenAI / Gemini cloud config');
}

function saveLlmSettings() {
  const apiKey = getVal('cfg-api-key');
  const baseUrl = getVal('cfg-base-url');
  const model = getVal('cfg-model');
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('lineagiq_api_key', apiKey);
    localStorage.setItem('lineagiq_base_url', baseUrl);
    localStorage.setItem('lineagiq_model', model);
  }
}

function loadLlmSettings() {
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

function applySuggestedPrompt(promptText) {
  const inputEl = getEl('chat-input');
  if (inputEl) inputEl.value = promptText;
  sendChatMessage();
}

async function sendChatMessage() {
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

    const bubble = aiLoadingDiv.querySelector('.msg-bubble');
    if (bubble) bubble.innerHTML = formatMarkdown(data.reply);

    if (data.target_node_id && typeof highlightConnected === 'function') {
      selectedNodeId = data.target_node_id;
      highlightConnected(data.target_node_id);
    }
  } catch (err) {
    const bubble = aiLoadingDiv.querySelector('.msg-bubble');
    if (bubble) bubble.innerHTML = `<span style="color: var(--accent-rose);">Error: ${escapeHtml(err.message)}</span>`;
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

  // Multiline code blocks ```...```
  html = html.replace(/```(?:[a-zA-Z0-9_-]+)?\n?([\s\S]*?)```/g, (match, code) => {
    return `<pre style="background: rgba(2, 6, 23, 0.7); padding: 8px 12px; border-radius: 6px; overflow-x: auto; border: 1px solid var(--border-subtle); margin: 6px 0; font-family: 'Fira Code', monospace; font-size: 12px; color: #38bdf8;"><code>${code.trim()}</code></pre>`;
  });

  // Inline code `...`
  html = html.replace(/`([^`]+)`/g, "<code style='background: rgba(2, 6, 23, 0.6); color: #38bdf8; padding: 2px 6px; border-radius: 4px;'>$1</code>");

  // Bold **...**
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

  // LaTeX & Math arrows and symbols (e.g. $\rightarrow$, \rightarrow, $\to$, $\leftarrow$)
  html = html.replace(/\$\s*\\+(?:rightarrow|to)\s*\$/g, "→");
  html = html.replace(/\\+(?:rightarrow|to)\b/g, "→");
  html = html.replace(/\$\s*\\+leftarrow\s*\$/g, "←");
  html = html.replace(/\\+leftarrow\b/g, "←");
  html = html.replace(/\$\s*\\+Rightarrow\s*\$/g, "⇒");
  html = html.replace(/\\+Rightarrow\b/g, "⇒");
  html = html.replace(/\$\s*\\+Leftarrow\s*\$/g, "⇐");
  html = html.replace(/\\+Leftarrow\b/g, "⇐");
  html = html.replace(/\$\s*\\+leftrightarrow\s*\$/g, "↔");
  html = html.replace(/\\+leftrightarrow\b/g, "↔");
  html = html.replace(/\$\s*\\+Leftrightarrow\s*\$/g, "⇔");
  html = html.replace(/\\+Leftrightarrow\b/g, "⇔");
  html = html.replace(/\$\s*\\+(?:longrightarrow|mapsto|implies)\s*\$/g, "⟶");
  html = html.replace(/\\+(?:longrightarrow|mapsto|implies)\b/g, "⟶");
  html = html.replace(/\$([^$\n]*?[→←⇒⇐↔⇔⟶⟵⟹↦][^$\n]*?)\$/g, "$1");
  html = html.replace(/\{([→←⇒⇐↔⇔⟶⟵⟹↦])\}/g, "$1");

  html = html.replace(/\n/g, "<br>");
  return html;
}

function openTimeDiffModal() {
  const modal = getEl('time-diff-modal');
  if (modal) modal.style.display = 'flex';
  populateDiffDropdowns();
}

function closeTimeDiffModal() {
  const modal = getEl('time-diff-modal');
  if (modal) modal.style.display = 'none';
}

function populateDiffDropdowns() {
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
  if (selectedNodeId && nodeInput) {
    nodeInput.value = selectedNodeId;
  }
}

async function executeTimeDiff() {
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

    applyGraphDiffVisuals(diff);
  } catch (err) {
    alert(`Error executing time diff: ${err.message}`);
  }
}

function switchDiffTab(tabName) {
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
  const drawer = getEl('chat-drawer');
  if (drawer) drawer.style.display = 'flex';

  const inputEl = getEl('chat-input');
  if (inputEl) inputEl.value = `Analyze historical schema drift and lineage changes:\n\n${lastDiffResult.synthesized_prompt}`;
  sendChatMessage();
}

if (typeof window !== 'undefined') {
  window.addEventListener('DOMContentLoaded', () => {
    loadLlmSettings();
    loadGraph();
  });
  window.addEventListener('resize', updateChatDrawerPosition);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    escapeHtml,
    formatMarkdown,
    switchDiffTab,
    typeColors,
    parseNodeProperties,
    buildColumnToDatasetMap,
    onTimelineSliderChange,
    resetTimelineLive,
    displayNodeDetails,
    resetSidebar,
    saveLlmSettings,
    loadLlmSettings,
    applySuggestedPrompt,
    computeDeterministicPositions,
    updateChatDrawerPosition,
    toggleChatDockMode,
    setOllamaConfig,
    setOpenAiConfig
  };
}
