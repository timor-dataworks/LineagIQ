"""Pure NumPy & Apache Arrow In-Memory Implementation of BaseGraphStore.

Uses Compressed Sparse Row (CSR) and Compressed Sparse Column (CSC) array layouts
for ultra-fast microsecond graph traversals, reachability trees, and memory-efficient caching.
"""

import json
import logging
import os
import threading
from typing import Any

import numpy as np
import pyarrow as pa
from deltalake import DeltaTable

from control_plane.src.query_engine.base import BaseGraphStore
from core.constants import (
    FILE_DATA_PARQUET,
    get_edges_table_path,
    get_nodes_table_path,
)
from core.utils import extract_search_terms, parse_iso_to_epoch_ms

logger = logging.getLogger(__name__)


class _NumpyGraphSnapshot:
    """Immutable in-memory graph snapshot backed by NumPy CSR/CSC arrays."""

    def __init__(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> None:
        self.nodes = nodes
        self.edges = edges
        self.num_nodes = len(nodes)
        self.num_edges = len(edges)

        # 1. ID <-> Index Mapping
        self.id_to_idx: dict[str, int] = {}
        self.idx_to_id: list[str] = []
        for i, n in enumerate(nodes):
            nid = n["id"]
            self.id_to_idx[nid] = i
            self.idx_to_id.append(nid)

        # Also register any external IDs referenced in edges that were missing in nodes
        for e in edges:
            s_id = e["source_id"]
            t_id = e["target_id"]
            if s_id not in self.id_to_idx:
                idx = len(self.idx_to_id)
                self.id_to_idx[s_id] = idx
                self.idx_to_id.append(s_id)
                name = s_id.split(".")[-1] if "." in s_id else s_id
                ntype = "Dataset" if any(k in s_id.lower() for k in ["source", "raw", "db.", "table"]) else "Pipeline"
                self.nodes.append(
                    {
                        "id": s_id,
                        "type": ntype,
                        "name": name,
                        "description": f"External Data Asset / Source ({s_id})",
                        "properties": json.dumps({"source": "lineage_traversal"}),
                    }
                )
            if t_id not in self.id_to_idx:
                idx = len(self.idx_to_id)
                self.id_to_idx[t_id] = idx
                self.idx_to_id.append(t_id)
                name = t_id.split(".")[-1] if "." in t_id else t_id
                ntype = "Dataset" if any(k in t_id.lower() for k in ["source", "raw", "db.", "table"]) else "Pipeline"
                self.nodes.append(
                    {
                        "id": t_id,
                        "type": ntype,
                        "name": name,
                        "description": f"External Data Asset / Source ({t_id})",
                        "properties": json.dumps({"source": "lineage_traversal"}),
                    }
                )

        self.num_nodes = len(self.nodes)
        total_n = self.num_nodes

        # 2. Build Forward CSR (downstream) & Backward CSR (upstream)
        src_all: list[int] = []
        dst_all: list[int] = []
        src_lineage: list[int] = []
        dst_lineage: list[int] = []
        self.edge_type_map: dict[tuple[int, int], str] = {}

        for e in edges:
            s_id = e["source_id"]
            t_id = e["target_id"]
            e_type = e.get("type", "DEPENDS_ON")
            s_idx = self.id_to_idx[s_id]
            t_idx = self.id_to_idx[t_id]
            self.edge_type_map[(s_idx, t_idx)] = e_type

            src_all.append(s_idx)
            dst_all.append(t_idx)

            if e_type != "BELONGS_TO":
                src_lineage.append(s_idx)
                dst_lineage.append(t_idx)

        # 2a. Forward All CSR (for hop 1 anchor traversal)
        if src_all:
            src_arr = np.array(src_all, dtype=np.int32)
            dst_arr = np.array(dst_all, dtype=np.int32)
            fwd_order = np.argsort(src_arr)
            self.fwd_all_sources = src_arr[fwd_order]
            self.fwd_all_targets = dst_arr[fwd_order]
            fwd_counts = np.bincount(self.fwd_all_sources, minlength=total_n)
            self.fwd_all_indptr = np.zeros(total_n + 1, dtype=np.int32)
            self.fwd_all_indptr[1:] = np.cumsum(fwd_counts)
        else:
            self.fwd_all_indptr = np.zeros(total_n + 1, dtype=np.int32)
            self.fwd_all_targets = np.empty(0, dtype=np.int32)

        # 2b. Forward Lineage CSR (for hop >= 2 traversal) & Backward CSR (lineage only)
        if src_lineage:
            src_l_arr = np.array(src_lineage, dtype=np.int32)
            dst_l_arr = np.array(dst_lineage, dtype=np.int32)
            fwd_l_order = np.argsort(src_l_arr)
            self.fwd_lineage_sources = src_l_arr[fwd_l_order]
            self.fwd_lineage_targets = dst_l_arr[fwd_l_order]
            fwd_l_counts = np.bincount(self.fwd_lineage_sources, minlength=total_n)
            self.fwd_lineage_indptr = np.zeros(total_n + 1, dtype=np.int32)
            self.fwd_lineage_indptr[1:] = np.cumsum(fwd_l_counts)

            # Build Backward CSR (always lineage only)
            bwd_order = np.argsort(dst_l_arr)
            self.bwd_targets = dst_l_arr[bwd_order]
            self.bwd_sources = src_l_arr[bwd_order]
            bwd_counts = np.bincount(self.bwd_targets, minlength=total_n)
            self.bwd_indptr = np.zeros(total_n + 1, dtype=np.int32)
            self.bwd_indptr[1:] = np.cumsum(bwd_counts)
        else:
            self.fwd_lineage_indptr = np.zeros(total_n + 1, dtype=np.int32)
            self.fwd_lineage_targets = np.empty(0, dtype=np.int32)
            self.bwd_indptr = np.zeros(total_n + 1, dtype=np.int32)
            self.bwd_sources = np.empty(0, dtype=np.int32)

        # Fast lookup mapping for nodes
        self.node_dict = {n["id"]: n for n in self.nodes}

    def memory_footprint_bytes(self) -> int:
        """Computes approximate RAM footprint of the NumPy CSR structures."""
        return int(
            self.fwd_all_indptr.nbytes
            + self.fwd_all_targets.nbytes
            + self.fwd_lineage_indptr.nbytes
            + self.fwd_lineage_targets.nbytes
            + self.bwd_indptr.nbytes
            + self.bwd_sources.nbytes
        )


class NumpyGraphStore(BaseGraphStore):
    """Pure NumPy & Apache Arrow In-Memory Implementation of `BaseGraphStore`.

    Loads Delta Lake tables into CSR (Compressed Sparse Row) and CSC arrays in RAM.
    Executes BFS graph reachability traversals with sub-millisecond latencies.

    Args:
        data_base_path: Root directory path or S3 URI where Delta Lake graph tables reside.
        storage_options: Optional cloud storage backend configurations (S3 credentials, endpoint).
    """

    def __init__(
        self,
        data_base_path: str,
        storage_options: dict[str, Any] | None = None,
    ) -> None:
        self.base_path = data_base_path
        self.storage_options = storage_options or {}
        self.is_s3 = data_base_path.startswith("s3://")
        if self.is_s3:
            base_clean = data_base_path.rstrip("/")
            self.nodes_dir = f"{base_clean}/graph/nodes"
            self.edges_dir = f"{base_clean}/graph/edges"
        else:
            self.nodes_dir = get_nodes_table_path(data_base_path)
            self.edges_dir = get_edges_table_path(data_base_path)

        self._snapshot_cache: dict[str | None, _NumpyGraphSnapshot] = {}
        self._cache_lock = threading.Lock()

    def _resolve_target_version(self, dt: DeltaTable, as_of: str | None) -> tuple[int | None, bool]:
        """Resolves target version number and whether as_of precedes all history.

        Returns: (target_version, is_before_history)
        """
        if as_of is None:
            return None, False
        if isinstance(as_of, int) or (isinstance(as_of, str) and as_of.isdigit()):
            return int(as_of), False

        target_ms = parse_iso_to_epoch_ms(as_of)
        if target_ms is None:
            return None, False

        try:
            history = dt.history()
        except Exception:
            return None, False

        if not history:
            return None, False

        sorted_commits = sorted(history, key=lambda x: x.get("timestamp", 0))
        earliest_ms = sorted_commits[0].get("timestamp", 0)
        if target_ms + 100 < earliest_ms:
            return None, True

        target_ver = sorted_commits[0].get("version", 0)
        for commit in sorted_commits:
            commit_ms = commit.get("timestamp", 0)
            if commit_ms <= target_ms + 100:
                target_ver = commit.get("version", 0)
        return target_ver, False

    def _load_snapshot(self, as_of: str | None = None) -> _NumpyGraphSnapshot | None:
        """Loads and caches in-memory NumPy graph snapshot from Delta/Parquet tables."""
        cache_key = as_of
        with self._cache_lock:
            if cache_key in self._snapshot_cache:
                return self._snapshot_cache[cache_key]

            # 1. Resolve tables via DeltaTable or Parquet
            nodes_records: list[dict[str, Any]] = []
            edges_records: list[dict[str, Any]] = []

            # Load Nodes
            try:
                if os.path.exists(self.nodes_dir) and DeltaTable.is_deltatable(self.nodes_dir):
                    dt_nodes = DeltaTable(self.nodes_dir, storage_options=self.storage_options)
                    target_ver, is_before = self._resolve_target_version(dt_nodes, as_of)
                    if is_before:
                        nodes_records = []
                    else:
                        if target_ver is not None:
                            dt_nodes.load_as_version(target_ver)
                        arrow_nodes = dt_nodes.to_pyarrow_table()
                        raw_nodes = arrow_nodes.to_pylist()
                        # Deduplicate nodes by ID (latest appended row wins)
                        seen_nodes: dict[str, dict[str, Any]] = {}
                        for n in raw_nodes:
                            seen_nodes[n["id"]] = n
                        nodes_records = list(seen_nodes.values())
                else:
                    parquet_nodes = os.path.join(self.nodes_dir, FILE_DATA_PARQUET)
                    if os.path.exists(parquet_nodes):
                        nodes_records = pa.parquet.read_table(parquet_nodes).to_pylist()
            except Exception as e:
                logger.warning(f"NumpyGraphStore could not read nodes table at {self.nodes_dir}: {e}")

            # Load Edges
            try:
                if os.path.exists(self.edges_dir) and DeltaTable.is_deltatable(self.edges_dir):
                    dt_edges = DeltaTable(self.edges_dir, storage_options=self.storage_options)
                    target_ver, is_before = self._resolve_target_version(dt_edges, as_of)
                    if is_before:
                        edges_records = []
                    else:
                        if target_ver is not None:
                            dt_edges.load_as_version(target_ver)
                        arrow_edges = dt_edges.to_pyarrow_table()
                        raw_edges = arrow_edges.to_pylist()
                        # Deduplicate edges by (source_id, target_id, type)
                        seen_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
                        for e in raw_edges:
                            key = (e["source_id"], e["target_id"], e.get("type", "DEPENDS_ON"))
                            seen_edges[key] = e
                        edges_records = list(seen_edges.values())
                else:
                    parquet_edges = os.path.join(self.edges_dir, FILE_DATA_PARQUET)
                    if os.path.exists(parquet_edges):
                        edges_records = pa.parquet.read_table(parquet_edges).to_pylist()
            except Exception as e:
                logger.warning(f"NumpyGraphStore could not read edges table at {self.edges_dir}: {e}")

            if not nodes_records and not edges_records:
                empty_snap = _NumpyGraphSnapshot(nodes=[], edges=[])
                self._snapshot_cache[cache_key] = empty_snap
                return empty_snap

            snapshot = _NumpyGraphSnapshot(nodes=nodes_records, edges=edges_records)
            self._snapshot_cache[cache_key] = snapshot
            return snapshot

    def get_full_graph(self, as_of: str | None = None) -> dict[str, Any]:
        """Retrieves all graph nodes and edges as of optional ISO 8601 timestamp."""
        snapshot = self._load_snapshot(as_of=as_of)
        if not snapshot:
            return {"nodes": [], "edges": []}
        return {"nodes": list(snapshot.nodes), "edges": list(snapshot.edges)}

    def get_downstream_blast_radius(
        self, start_node_id: str, max_depth: int = 5, as_of: str | None = None
    ) -> dict[str, Any]:
        """Computes downstream operational blast radius starting from a target node using NumPy CSR arrays."""
        snapshot = self._load_snapshot(as_of=as_of)
        if not snapshot or start_node_id not in snapshot.id_to_idx:
            return {"impacted_nodes": [], "edges": [], "root_node": None, "depth_reached": 0}

        start_idx = snapshot.id_to_idx[start_node_id]
        safe_depth = max(1, min(max_depth, 10))

        # BFS Traversal
        visited_indices: set[int] = {start_idx}
        frontier: list[int] = [start_idx]
        traversal_edges: list[dict[str, Any]] = []
        depth_reached = 0

        for d in range(1, safe_depth + 1):
            next_frontier: list[int] = []
            indptr = snapshot.fwd_all_indptr if d == 1 else snapshot.fwd_lineage_indptr
            targets = snapshot.fwd_all_targets if d == 1 else snapshot.fwd_lineage_targets
            for u in frontier:
                start_ptr = indptr[u]
                end_ptr = indptr[u + 1]
                neighbors = targets[start_ptr:end_ptr]
                for v in neighbors:
                    v_int = int(v)
                    e_type = snapshot.edge_type_map.get((u, v_int), "DEPENDS_ON")
                    traversal_edges.append(
                        {
                            "source_id": snapshot.idx_to_id[u],
                            "target_id": snapshot.idx_to_id[v_int],
                            "type": e_type,
                            "depth": d,
                        }
                    )
                    if v_int not in visited_indices:
                        visited_indices.add(v_int)
                        next_frontier.append(v_int)
            if not next_frontier:
                break
            depth_reached = d
            frontier = next_frontier

        impacted_nodes = [snapshot.nodes[idx] for idx in visited_indices if idx < len(snapshot.nodes)]
        root_node = snapshot.node_dict.get(start_node_id)

        return {
            "root_node": root_node,
            "impacted_nodes": impacted_nodes,
            "edges": traversal_edges,
            "depth_reached": depth_reached,
        }

    def get_upstream_root_cause(
        self, start_node_id: str, max_depth: int = 5, as_of: str | None = None
    ) -> dict[str, Any]:
        """Computes upstream root cause dependencies starting from a target node using NumPy CSC arrays."""
        snapshot = self._load_snapshot(as_of=as_of)
        if not snapshot or start_node_id not in snapshot.id_to_idx:
            return {"upstream_nodes": [], "edges": [], "target_node": None, "depth_reached": 0}

        start_idx = snapshot.id_to_idx[start_node_id]
        safe_depth = max(1, min(max_depth, 10))

        visited_indices: set[int] = {start_idx}
        frontier: list[int] = [start_idx]
        traversal_edges: list[dict[str, Any]] = []
        depth_reached = 0

        for d in range(1, safe_depth + 1):
            next_frontier: list[int] = []
            for u in frontier:
                start_ptr = snapshot.bwd_indptr[u]
                end_ptr = snapshot.bwd_indptr[u + 1]
                ancestors = snapshot.bwd_sources[start_ptr:end_ptr]
                for v in ancestors:
                    v_int = int(v)
                    e_type = snapshot.edge_type_map.get((v_int, u), "DEPENDS_ON")
                    traversal_edges.append(
                        {
                            "source_id": snapshot.idx_to_id[v_int],
                            "target_id": snapshot.idx_to_id[u],
                            "type": e_type,
                            "depth": d,
                        }
                    )
                    if v_int not in visited_indices:
                        visited_indices.add(v_int)
                        next_frontier.append(v_int)
            if not next_frontier:
                break
            depth_reached = d
            frontier = next_frontier

        upstream_nodes = [snapshot.nodes[idx] for idx in visited_indices if idx < len(snapshot.nodes)]
        target_node = snapshot.node_dict.get(start_node_id)

        return {
            "target_node": target_node,
            "upstream_nodes": upstream_nodes,
            "edges": traversal_edges,
            "depth_reached": depth_reached,
        }

    def get_nodes_by_ids(self, node_ids: list[str], as_of: str | None = None) -> list[dict[str, Any]]:
        """Retrieves full node metadata dicts matching given node_ids."""
        snapshot = self._load_snapshot(as_of=as_of)
        if not snapshot:
            return []
        return [snapshot.node_dict[nid] for nid in node_ids if nid in snapshot.node_dict]

    def search_nodes_by_terms(self, query_text: str, top_k: int = 5, as_of: str | None = None) -> list[dict[str, Any]]:
        """Searches node metadata fields for matching keywords."""
        snapshot = self._load_snapshot(as_of=as_of)
        if not snapshot or not query_text or not query_text.strip():
            return []

        terms = extract_search_terms(query_text)
        if not terms:
            return []

        scored_nodes: list[tuple[int, dict[str, Any]]] = []
        for n in snapshot.nodes:
            score = 0
            n_name = (n.get("name") or "").lower()
            n_id = (n.get("id") or "").lower()
            n_desc = (n.get("description") or "").lower()
            n_type = (n.get("type") or "").lower()
            n_props = str(n.get("properties") or "").lower()

            for t in terms:
                t_lower = t.lower()
                if t_lower in n_name:
                    score += 5
                if t_lower in n_id:
                    score += 4
                if t_lower in n_desc:
                    score += 2
                if t_lower in n_type:
                    score += 1
                if t_lower in n_props:
                    score += 1

            if score > 0:
                scored_nodes.append((score, n))

        scored_nodes.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in scored_nodes[: top_k * 2]]

    def _get_scoped_node_ids(
        self, graph: dict[str, Any], start_node_id: str | None, as_of: str | None = None
    ) -> set[str]:
        """Helper to compute set of node IDs connected to start_node_id (upstream + downstream)."""
        nodes = graph.get("nodes", [])
        if not nodes or not start_node_id:
            return {n["id"] for n in nodes}

        clean_start = start_node_id.strip().lower()
        if not clean_start or clean_start in ["all", "enterprise", "global", "none"]:
            return {n["id"] for n in nodes}

        matched_target_ids = {
            n["id"] for n in nodes if clean_start == n.get("id", "").lower() or clean_start == n.get("name", "").lower()
        }
        if not matched_target_ids:
            for n in nodes:
                nid = n.get("id", "").lower()
                name = n.get("name", "").lower()
                if clean_start in nid or clean_start in name:
                    matched_target_ids.add(n["id"])

        if not matched_target_ids:
            return set()

        scoped_ids = set(matched_target_ids)
        for target_id in matched_target_ids:
            blast = self.get_downstream_blast_radius(start_node_id=target_id, max_depth=5, as_of=as_of)
            root_cause = self.get_upstream_root_cause(start_node_id=target_id, max_depth=5, as_of=as_of)

            for n in blast.get("impacted_nodes", []):
                scoped_ids.add(n["id"])
            for n in root_cause.get("upstream_nodes", []):
                scoped_ids.add(n["id"])

        # Include all column nodes belonging to any scoped dataset node
        for e in graph.get("edges", []):
            if e.get("type") == "BELONGS_TO" and e.get("target_id") in scoped_ids:
                scoped_ids.add(e["source_id"])

        return scoped_ids

    def get_schema_time_travel_diff(
        self, start_node_id: str | None, timestamp_t1: str, timestamp_t2: str
    ) -> dict[str, Any]:
        """Computes schema and lineage graph diff between two historical ISO 8601 timestamps."""
        graph_t1 = self.get_full_graph(as_of=timestamp_t1)
        graph_t2 = self.get_full_graph(as_of=timestamp_t2)

        target_clean = (start_node_id or "").strip()
        is_global = not target_clean or target_clean.lower() in ["all", "enterprise", "global", "none"]

        if is_global:
            scoped_ids_t1 = {n["id"] for n in graph_t1.get("nodes", [])}
            scoped_ids_t2 = {n["id"] for n in graph_t2.get("nodes", [])}
        else:
            scoped_ids_t1 = self._get_scoped_node_ids(graph_t1, target_clean, as_of=timestamp_t1)
            scoped_ids_t2 = self._get_scoped_node_ids(graph_t2, target_clean, as_of=timestamp_t2)

        nodes_t1 = {n["id"]: n for n in graph_t1.get("nodes", []) if n["id"] in scoped_ids_t1}
        nodes_t2 = {n["id"]: n for n in graph_t2.get("nodes", []) if n["id"] in scoped_ids_t2}

        added_nodes = [n for nid, n in nodes_t2.items() if nid not in nodes_t1]
        removed_nodes = [n for nid, n in nodes_t1.items() if nid not in nodes_t2]

        modified_nodes = []
        for nid, n2 in nodes_t2.items():
            if nid in nodes_t1:
                n1 = nodes_t1[nid]
                if (
                    n1.get("name") != n2.get("name")
                    or n1.get("type") != n2.get("type")
                    or n1.get("properties") != n2.get("properties")
                    or n1.get("description") != n2.get("description")
                ):
                    modified_nodes.append({"id": nid, "before": n1, "after": n2})

        edges_t1 = {
            (e["source_id"], e["target_id"], e["type"])
            for e in graph_t1.get("edges", [])
            if e["source_id"] in scoped_ids_t1 or e["target_id"] in scoped_ids_t1
        }
        edges_t2 = {
            (e["source_id"], e["target_id"], e["type"])
            for e in graph_t2.get("edges", [])
            if e["source_id"] in scoped_ids_t2 or e["target_id"] in scoped_ids_t2
        }

        added_edges = [
            {"source_id": s, "target_id": t, "type": ty} for (s, t, ty) in edges_t2 if (s, t, ty) not in edges_t1
        ]
        removed_edges = [
            {"source_id": s, "target_id": t, "type": ty} for (s, t, ty) in edges_t1 if (s, t, ty) not in edges_t2
        ]

        return {
            "start_node_id": start_node_id,
            "timestamp_t1": timestamp_t1,
            "timestamp_t2": timestamp_t2,
            "added_nodes_count": len(added_nodes),
            "removed_nodes_count": len(removed_nodes),
            "modified_nodes_count": len(modified_nodes),
            "added_nodes": added_nodes,
            "removed_nodes": removed_nodes,
            "modified_nodes": modified_nodes,
            "added_edges": added_edges,
            "removed_edges": removed_edges,
        }

    def get_available_timestamps(self) -> list[dict[str, Any]]:
        """Retrieves commit history timestamps from tenant Delta Lake table logs."""
        if not os.path.exists(self.nodes_dir) or not DeltaTable.is_deltatable(self.nodes_dir):
            return []
        try:
            dt = DeltaTable(self.nodes_dir, storage_options=self.storage_options)
            history = dt.history()
            import datetime

            results = []
            for commit in sorted(history, key=lambda x: x.get("version", 0)):
                commit_ms = commit.get("timestamp", 0)
                dt_obj = datetime.datetime.fromtimestamp(commit_ms / 1000, tz=datetime.UTC)
                iso_str = dt_obj.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                results.append(
                    {
                        "version": commit.get("version", 0),
                        "timestamp": iso_str,
                        "timestamp_ms": commit_ms,
                        "operation": commit.get("operation", "WRITE"),
                    }
                )
            return results
        except Exception as e:
            logger.warning(f"NumpyGraphStore could not read history timestamps: {e}")
            return []

    def get_in_memory_footprint_bytes(self) -> int:
        """Returns total memory allocated in NumPy CSR arrays across cached snapshots."""
        with self._cache_lock:
            return sum(snap.memory_footprint_bytes() for snap in self._snapshot_cache.values())
