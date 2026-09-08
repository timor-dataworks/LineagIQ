import pytest
from collection_agent.src.embedder.local_embedder import LocalEmbedder
from collection_agent.src.transform.models import DatasetNode, ColumnNode, GraphPayload


def test_local_embedder_vector_generation():
    embedder = LocalEmbedder()
    vec = embedder.embed_text("Type: Dataset | Name: stg_customers | Description: Customer table")

    assert len(vec) == 384
    # Check L2 normalized magnitude approximately 1.0
    norm = sum(x * x for x in vec) ** 0.5
    assert pytest.approx(norm, abs=1e-3) == 1.0


def test_local_embedder_payload():
    ds_node = DatasetNode(id="ds1", name="orders", description="Order transactions")
    col_node = ColumnNode(id="col1", name="id", dataset_id="ds1")
    payload = GraphPayload(nodes=[ds_node, col_node], edges=[])

    embedder = LocalEmbedder()
    embedded_payload = embedder.embed_payload(payload)

    for node in embedded_payload.nodes:
        assert node.embedding is not None
        assert len(node.embedding) == 384


def create_dummy_onnx_embedding_model(filepath: str):
    import onnx
    from onnx import helper, TensorProto
    import numpy as np

    weights = np.random.randn(30522, 384).astype(np.float32)
    weight_initializer = helper.make_tensor(
        name="weight",
        data_type=TensorProto.FLOAT,
        dims=[30522, 384],
        vals=weights.tobytes(),
        raw=True,
    )

    input_tensor = helper.make_tensor_value_info("input_ids", TensorProto.INT64, [1, None])
    output_tensor = helper.make_tensor_value_info("embeddings", TensorProto.FLOAT, [1, None, 384])

    gather_node = helper.make_node("Gather", inputs=["weight", "input_ids"], outputs=["embeddings"], axis=0)

    graph = helper.make_graph([gather_node], "embedding_graph", [input_tensor], [output_tensor], [weight_initializer])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 14)])
    model.ir_version = 8

    onnx.save(model, filepath)


def test_local_embedder_onnx_runtime_inference(tmp_path):
    model_file = str(tmp_path / "embedding_model.onnx")
    create_dummy_onnx_embedding_model(model_file)

    embedder = LocalEmbedder(model_path=model_file)
    assert embedder._onnx_session is not None

    vec = embedder.embed_text("Test actual ONNX runtime text")

    assert len(vec) == 384
    # Check L2 normalization
    norm = sum(x * x for x in vec) ** 0.5
    assert pytest.approx(norm, abs=1e-3) == 1.0


def test_local_embedder_production_onnx_model(tmp_path):
    import os
    import urllib.request

    # Test against production quantized all-MiniLM-L6-v2 ONNX model
    model_url = "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/onnx/model_quantized.onnx"
    dest = os.path.join(str(tmp_path), "all-MiniLM-L6-v2-quantized.onnx")
    
    try:
        urllib.request.urlretrieve(model_url, dest)
    except Exception as e:
        pytest.skip(f"Network error downloading production ONNX model: {e}")

    embedder = LocalEmbedder(model_path=dest)
    assert embedder._onnx_session is not None

    vec = embedder.embed_text("Type: Dataset | Name: raw_customers | Description: Raw landing customer records")

    assert len(vec) == 384
    norm = sum(x * x for x in vec) ** 0.5
    assert pytest.approx(norm, abs=1e-3) == 1.0


