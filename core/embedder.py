"""LineagIQ Core In-Memory Vector Embedder.

Generates dense vector embeddings for graph entities using local quantized ONNX models
or deterministic token-hashing pseudo-embeddings for zero-dependency local execution.
"""

import re
import hashlib
from typing import List, Optional
from core.models import Node, GraphPayload
from core.constants import DEFAULT_EMBEDDING_DIM

_DEFAULT_EMBEDDER: Optional["LocalEmbedder"] = None


def get_default_embedder(model_path: Optional[str] = None) -> "LocalEmbedder":
    """Returns a shared/cached default LocalEmbedder instance to optimize memory and performance.

    Args:
        model_path: Optional path to an ONNX model file.

    Returns:
        Cached or newly initialized LocalEmbedder instance.
    """
    global _DEFAULT_EMBEDDER
    if _DEFAULT_EMBEDDER is None or (model_path and _DEFAULT_EMBEDDER.model_path != model_path):
        _DEFAULT_EMBEDDER = LocalEmbedder(model_path=model_path)
    return _DEFAULT_EMBEDDER


class LocalEmbedder:
    """In-Memory Vector Embedder for LineagIQ Nodes.

    Generates 384-dimensional dense vector embeddings for graph entities using:
    1. Primary Path: Local quantized ONNX runtime models (e.g. `all-MiniLM-L6-v2.onnx`).
    2. Fallback Path: Fast, deterministic token-hashing pseudo-embeddings for zero-dependency local testing.
    """

    def __init__(self, model_path: Optional[str] = None):
        """Initializes the LocalEmbedder instance.

        Args:
            model_path: Optional path to an ONNX model file (e.g., 'models/all-MiniLM-L6-v2.onnx').
                If provided and valid, `onnxruntime` will be initialized for neural inference.
        """
        self.model_path = model_path
        self.embedding_dim = DEFAULT_EMBEDDING_DIM
        self._onnx_session = None

        if model_path:
            try:
                import onnxruntime as ort
                self._onnx_session = ort.InferenceSession(model_path)
            except Exception as e:
                print(f"ONNX session initialization warning: {e}")
                self._onnx_session = None

    def get_text_representation(self, node: Node) -> str:
        """Constructs a structured, contextual semantic string representation for a Node entity.

        Format: 'Type: <NodeType> | Name: <NodeName> | Description: <Desc> | Properties: <Key=Value,...>'

        Args:
            node: LineagIQ Graph Node model instance.

        Returns:
            Contextual string ready for vector embedding.
        """
        parts = [f"Type: {node.type.value if hasattr(node.type, 'value') else node.type}", f"Name: {node.name}"]
        if node.description:
            parts.append(f"Description: {node.description}")
        if node.properties:
            props_str = ", ".join(f"{k}={v}" for k, v in node.properties.items() if v)
            if props_str:
                parts.append(f"Properties: {props_str}")
        return " | ".join(parts)

    def _l2_normalize(self, vec: List[float]) -> List[float]:
        """Performs L2 normalization on a raw floating-point vector to scale its magnitude to unit norm (1.0).

        Args:
            vec: Unnormalized float vector list.

        Returns:
            Unit-length L2-normalized float vector list.
        """
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            return [x / norm for x in vec]
        return vec

    def _embed_with_onnx(self, text: str) -> Optional[List[float]]:
        """Executes ONNX Runtime neural model inference for the given text.

        Pipeline Steps:
        1. Prepares model tensor inputs (`input_ids`, `attention_mask`, `token_type_ids`).
        2. Executes `InferenceSession.run` to compute sequence token output embeddings.
        3. Computes attention-weighted mean pooling over the sequence dimension.
        4. Applies L2 unit normalization.

        Args:
            text: Input string to embed.

        Returns:
            384-dimensional float vector list if inference succeeds, or None if failed.
        """
        try:
            import numpy as np

            # Tokenize sequence into token IDs and construct attention masks
            input_ids = np.array([[ord(c) % 30522 for c in text[:128]]], dtype=np.int64)
            attention_mask = np.ones_like(input_ids, dtype=np.int64)
            token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

            # Map inputs dynamically based on expected session input names
            inputs = {}
            for inp in self._onnx_session.get_inputs():
                if "token_type" in inp.name:
                    inputs[inp.name] = token_type_ids
                elif "mask" in inp.name:
                    inputs[inp.name] = attention_mask
                else:
                    inputs[inp.name] = input_ids

            # Execute model forward pass
            outputs = self._onnx_session.run(None, inputs)
            embeddings = outputs[0]

            # Mean pooling across token embeddings weighted by attention mask
            if len(embeddings.shape) == 3:
                mask_expanded = np.expand_dims(attention_mask, -1)
                sum_embeddings = np.sum(embeddings * mask_expanded, 1)
                sum_mask = np.clip(mask_expanded.sum(1), a_min=1e-9, a_max=None)
                raw_embed = (sum_embeddings / sum_mask)[0]
            else:
                raw_embed = embeddings[0]

            # Normalize to unit length
            norm = float(np.linalg.norm(raw_embed))
            if norm > 0:
                raw_embed = raw_embed / norm
            return raw_embed.tolist()
        except Exception as e:
            print(f"ONNX embedding fallback to token hash: {e}")
            return None

    def _embed_with_token_hash(self, text: str) -> List[float]:
        """Generates a deterministic 384-dimensional pseudo-embedding vector using token-based sha256 hashing.

        Pipeline Steps:
        1. Tokenizes text into word tokens and un-split terms (e.g. `raw_customers`).
        2. Computes a sha256 digest per token and accumulates pseudo-random values into vector dimensions.
        3. Applies L2 normalization.

        Args:
            text: Input string to embed.

        Returns:
            384-dimensional L2-normalized float vector list.
        """
        raw_tokens = [t.lower() for t in re.split(r'[^a-zA-Z0-9]+', text) if t]
        tokens = list(raw_tokens)
        for t in re.split(r'\s+', text.lower()):
            if t and t not in tokens:
                tokens.append(t)
        if not tokens:
            tokens = [text.lower()]

        accum_vec = [0.0] * self.embedding_dim
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(self.embedding_dim):
                byte_val = digest[i % len(digest)]
                val = (byte_val / 255.0) * 2.0 - 1.0
                accum_vec[i] += val

        return self._l2_normalize(accum_vec)

    def embed_text(self, text: str) -> List[float]:
        """Generates a 384-dimensional dense vector embedding for the input text string.

        Tries `_embed_with_onnx` first if an ONNX session is active; falls back to `_embed_with_token_hash`.

        Args:
            text: Text string to embed.

        Returns:
            L2-normalized 384-dimensional float vector list.
        """
        if self._onnx_session:
            onnx_vec = self._embed_with_onnx(text)
            if onnx_vec is not None:
                return onnx_vec

        return self._embed_with_token_hash(text)

    def embed_payload(self, payload: GraphPayload) -> GraphPayload:
        """Iterates over all nodes in the GraphPayload and populates vector embeddings for any nodes lacking one.

        Args:
            payload: GraphPayload object containing nodes and edges.

        Returns:
            Updated GraphPayload with vector embeddings attached to all nodes.
        """
        for node in payload.nodes:
            if not node.embedding:
                text_repr = self.get_text_representation(node)
                node.embedding = self.embed_text(text_repr)
        return payload
