/**
 * LineagIQ Control Plane - Knowledge Graph & DAG Visualization Module
 */

import { fetchGraph, searchDiscovery, fetchBlastRadius, fetchRootCause } from './api.js';
import { getEl, getVal, parseNodeProperties } from './utils.js';
import { updateChatDrawerPosition } from './chat.js';
import { loadTimeline, getCurrentAsOfTimestamp } from './timeline.js';

export let network = null;
export let nodesDataSet = null;
export let edgesDataSet = null;
export let rawNodes = [];
export let rawEdges = [];
export let selectedNodeId = null;
let searchDebounceTimer = null;
let vectorMatchedIds = null;

export function getSelectedNodeId() {
  return selectedNodeId;
}

export function setSelectedNodeId(id) {
  selectedNodeId = id;
}

export const typeColors = {
  'Dataset': { background: '#0284c7', border: 'transparent', highlight: '#06b6d4' },
  'Column': { background: '#7c3aed', border: 'transparent', highlight: '#a855f7' },
  'ColumnCloud': { background: '#2e1065', border: '#7c3aed', highlight: '#c084fc' },
  'Pipeline': { background: '#d97706', border: 'transparent', highlight: '#f59e0b' },
  'User': { background: '#059669', border: 'transparent', highlight: '#10b981' },
  'BusinessTerm': { background: '#e11d48', border: 'transparent', highlight: '#f43f5e' }
};

export function buildColumnToDatasetMap(nodes, edges) {
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

export async function loadGraph(refreshTimeline = true) {
  const asOf = getCurrentAsOfTimestamp();

  try {
    const data = await fetchGraph(asOf);
    rawNodes = data.nodes || [];
    rawEdges = data.edges || [];

    filterGraph();
    if (refreshTimeline) loadTimeline();
  } catch (err) {
    console.error("Error loading graph:", err);
  }
}

export function handleSearchInput() {
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

export async function performVectorSearch(queryText) {
  const asOf = getCurrentAsOfTimestamp();

  try {
    const data = await searchDiscovery(queryText, asOf);
    vectorMatchedIds = new Set((data.matched_nodes || []).map(n => n.id));
  } catch (err) {
    console.warn("Vector search fallback to local filter:", err);
    vectorMatchedIds = null;
  }

  filterGraph();
}

export function getViewMode() {
  const switchEl = getEl('view-mode-switch');
  if (switchEl) {
    return switchEl.checked ? 'high_level' : 'all';
  }
  const viewModeEl = getEl('view-mode');
  if (viewModeEl) {
    if (viewModeEl.type === 'checkbox') {
      return viewModeEl.checked ? 'high_level' : 'all';
    }
    return viewModeEl.value || 'high_level';
  }
  return 'high_level';
}

export function filterGraph() {
  const switchEl = getEl('view-mode-switch');
  if (switchEl && switchEl.setAttribute) {
    switchEl.setAttribute('aria-checked', switchEl.checked ? 'true' : 'false');
  }
  const viewMode = getViewMode();
  const hiddenInput = getEl('view-mode');
  if (hiddenInput && hiddenInput.type === 'hidden') {
    hiddenInput.value = viewMode;
  }
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

export function computeDagNodeLevels(nodes, edgesData) {
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

export function formatGraphNodes(nodesData, edgesData) {
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

export function formatGraphEdges(edgesData, columnToParentMap, columnCloudNodeMap, isHierarchical) {
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

export function computeDeterministicPositions(formattedNodes, formattedEdges, isHierarchical) {
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

export function renderNetwork(nodesData, edgesData) {
  const isHierarchical = (getVal('layout-mode') === 'hierarchical');

  const { formattedNodes, columnToParentMap, columnCloudNodeMap } = formatGraphNodes(nodesData, edgesData);
  const formattedEdges = formatGraphEdges(edgesData, columnToParentMap, columnCloudNodeMap, isHierarchical);

  computeDeterministicPositions(formattedNodes, formattedEdges, isHierarchical);

  if (isHierarchical) {
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

  if (typeof vis === 'undefined') return;

  nodesDataSet = new vis.DataSet(formattedNodes);
  edgesDataSet = new vis.DataSet(formattedEdges);

  const container = getEl('network-canvas');
  if (!container) return;

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

export function fitGraphView() {
  if (network) {
    network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
  }
}

export function toggleLayout() {
  filterGraph();
}

export function displayNodeDetails(node) {
  if (!node) return;
  const sidebar = getEl('sidebar');
  if (sidebar) sidebar.style.display = 'flex';

  const backdrop = getEl('drawer-backdrop');
  if (backdrop && typeof window !== 'undefined' && window.innerWidth <= 768) {
    backdrop.style.display = 'block';
  }

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

export function highlightConnected(nodeId) {
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

export function resetSidebar() {
  const sidebar = getEl('sidebar');
  if (sidebar) sidebar.style.display = 'none';

  const backdrop = getEl('drawer-backdrop');
  if (backdrop) backdrop.style.display = 'none';

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

export async function triggerBlastRadius() {
  if (!selectedNodeId) return;
  const blastBtn = getEl('blast-btn');

  try {
    if (blastBtn) {
      blastBtn.innerText = '⏳ Calculating Blast Radius...';
      blastBtn.disabled = true;
    }
    const result = await fetchBlastRadius(selectedNodeId, 5);

    const impactedIds = new Set((result.impacted_nodes || []).map(n => n.id));
    if (nodesDataSet) {
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
    }

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

export async function triggerRootCause() {
  if (!selectedNodeId) return;
  const rootBtn = getEl('root-cause-btn');

  try {
    if (rootBtn) {
      rootBtn.innerText = '⏳ Calculating Root Cause...';
      rootBtn.disabled = true;
    }
    const result = await fetchRootCause(selectedNodeId, 5);

    const upstreamIds = new Set((result.upstream_nodes || []).map(n => n.id));
    if (nodesDataSet) {
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
    }

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

export function resetGraphHighlight() {
  filterGraph();
  resetSidebar();
}

export function applyGraphDiffVisuals(diff) {
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

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
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
  };
}
