/**
 * LineagIQ Control Plane - API Service Module
 * Handles all network requests to FastAPI backend endpoints.
 */

export async function fetchGraph(tenantId, dataPath, asOfTimestamp) {
  let url = `/api/v1/tenants/${encodeURIComponent(tenantId)}/graph`;
  const params = [];
  if (dataPath) params.push(`data_path=${encodeURIComponent(dataPath)}`);
  if (asOfTimestamp) params.push(`as_of=${encodeURIComponent(asOfTimestamp)}`);
  if (params.length > 0) url += `?${params.join('&')}`;

  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch knowledge graph data.");
  return await response.json();
}

export async function fetchTimeline(tenantId, dataPath) {
  let url = `/api/v1/tenants/${encodeURIComponent(tenantId)}/timeline`;
  if (dataPath) url += `?data_path=${encodeURIComponent(dataPath)}`;

  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch timeline data.");
  return await response.json();
}

export async function searchDiscovery(tenantId, dataPath, queryText, asOfTimestamp) {
  const response = await fetch(`/api/v1/tenants/${encodeURIComponent(tenantId)}/discovery`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: queryText,
      top_k: 10,
      data_path: dataPath,
      as_of: asOfTimestamp || undefined,
    })
  });
  if (!response.ok) throw new Error("Vector search HTTP error");
  return await response.json();
}

export async function fetchBlastRadius(tenantId, dataPath, nodeId, maxDepth = 5) {
  const response = await fetch(`/api/v1/tenants/${encodeURIComponent(tenantId)}/blast-radius`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node_id: nodeId,
      max_depth: maxDepth,
      data_path: dataPath
    })
  });
  if (!response.ok) throw new Error("Blast radius calculation failed");
  return await response.json();
}

export async function fetchRootCause(tenantId, dataPath, nodeId, maxDepth = 5) {
  const response = await fetch(`/api/v1/tenants/${encodeURIComponent(tenantId)}/root-cause`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node_id: nodeId,
      max_depth: maxDepth,
      data_path: dataPath
    })
  });
  if (!response.ok) throw new Error("Root cause calculation failed");
  return await response.json();
}

export async function sendChat(tenantId, dataPath, message, llmConfig = {}) {
  const response = await fetch(`/api/v1/tenants/${encodeURIComponent(tenantId)}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: message,
      data_path: dataPath,
      openai_api_key: llmConfig.apiKey || undefined,
      openai_base_url: llmConfig.baseUrl || undefined,
      openai_model: llmConfig.model || undefined
    })
  });
  if (!response.ok) throw new Error("Chat request failed");
  return await response.json();
}

export async function fetchTimeDiff(tenantId, dataPath, nodeId, timestampT1, timestampT2) {
  const response = await fetch(`/api/v1/tenants/${encodeURIComponent(tenantId)}/time-travel/diff`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node_id: nodeId || undefined,
      timestamp_t1: timestampT1,
      timestamp_t2: timestampT2,
      data_path: dataPath
    })
  });
  if (!response.ok) throw new Error("Time Travel Diff request failed");
  return await response.json();
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    fetchGraph,
    fetchTimeline,
    searchDiscovery,
    fetchBlastRadius,
    fetchRootCause,
    sendChat,
    fetchTimeDiff
  };
}
