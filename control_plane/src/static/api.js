/**
 * LineagIQ Control Plane - API Service Module
 * Handles all network requests to FastAPI backend endpoints.
 * All data path and tenant configuration is strictly resolved server-side from environment variables.
 */

export async function fetchGraph(asOfTimestamp) {
  let url = `/api/v1/graph`;
  if (asOfTimestamp) url += `?as_of=${encodeURIComponent(asOfTimestamp)}`;

  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch knowledge graph data.");
  return await response.json();
}

export async function fetchTimeline() {
  const response = await fetch(`/api/v1/timeline`);
  if (!response.ok) throw new Error("Failed to fetch timeline data.");
  return await response.json();
}

export async function searchDiscovery(queryText, asOfTimestamp) {
  const response = await fetch(`/api/v1/discovery`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: queryText,
      top_k: 10,
      as_of: asOfTimestamp || undefined,
    })
  });
  if (!response.ok) throw new Error("Vector search HTTP error");
  return await response.json();
}

export async function fetchBlastRadius(nodeId, maxDepth = 5) {
  const response = await fetch(`/api/v1/blast-radius`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node_id: nodeId,
      max_depth: maxDepth
    })
  });
  if (!response.ok) throw new Error("Blast radius calculation failed");
  return await response.json();
}

export async function fetchRootCause(nodeId, maxDepth = 5) {
  const response = await fetch(`/api/v1/root-cause`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node_id: nodeId,
      max_depth: maxDepth
    })
  });
  if (!response.ok) throw new Error("Root cause calculation failed");
  return await response.json();
}

export async function sendChat(message, llmConfig = {}) {
  const response = await fetch(`/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: message,
      openai_api_key: llmConfig.apiKey || undefined,
      openai_base_url: llmConfig.baseUrl || undefined,
      openai_model: llmConfig.model || undefined
    })
  });
  if (!response.ok) throw new Error("Chat request failed");
  return await response.json();
}

export async function fetchTimeDiff(nodeId, timestampT1, timestampT2) {
  const response = await fetch(`/api/v1/time-travel/diff`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node_id: nodeId || undefined,
      timestamp_t1: timestampT1,
      timestamp_t2: timestampT2
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
