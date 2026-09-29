from control_plane.src.services.latex_sanitizer import clean_latex_to_unicode
from control_plane.src.services.llm_service import call_llm, call_openai_llm


def test_clean_latex_to_unicode_arrows():
    assert clean_latex_to_unicode("A $\\rightarrow$ B") == "A → B"
    assert clean_latex_to_unicode("A $\\to$ B") == "A → B"
    assert clean_latex_to_unicode("A \\rightarrow B") == "A → B"
    assert clean_latex_to_unicode("A $\\leftarrow$ B") == "A ← B"
    assert clean_latex_to_unicode("A $\\Rightarrow$ B") == "A ⇒ B"
    assert clean_latex_to_unicode("A $\\Leftarrow$ B") == "A ⇐ B"
    assert clean_latex_to_unicode("A $\\leftrightarrow$ B") == "A ↔ B"
    assert clean_latex_to_unicode("A $\\Leftrightarrow$ B") == "A ⇔ B"


def test_clean_latex_to_unicode_symbols_and_wrappers():
    assert clean_latex_to_unicode("$\\text{raw\\_table} \\rightarrow \\text{stg\\_table}$") == "raw_table → stg_table"
    assert clean_latex_to_unicode("\\mathbf{bold} \\mathit{italic}") == "bold italic"
    assert clean_latex_to_unicode("x $\\approx$ y") == "x ≈ y"
    assert clean_latex_to_unicode("x $\\neq$ y") == "x ≠ y"
    assert clean_latex_to_unicode("x $\\le$ y and a $\\ge$ b") == "x ≤ y and a ≥ b"
    assert clean_latex_to_unicode("a $\\times$ b $\\cdot$ c $\\dots$") == "a × b · c ..."
    assert clean_latex_to_unicode(None) is None
    assert clean_latex_to_unicode("") == ""


def test_call_llm_without_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    res, err = call_llm("test prompt")
    assert res is None
    assert err is None


def test_call_openai_llm_with_mocked_post(monkeypatch):
    def mock_post_json(url, payload, headers=None, timeout=45):
        assert "chat/completions" in url
        assert payload["model"] == "test-model"
        return {"choices": [{"message": {"content": "Lineage analysis: raw $\\rightarrow$ analytics"}}]}, None

    monkeypatch.setattr("control_plane.src.services.llm_service.post_json", mock_post_json)

    res, err = call_openai_llm(
        prompt="Analyze lineage",
        api_key="sk-test-key",
        model="test-model",
    )
    assert err is None
    assert res == "Lineage analysis: raw → analytics"


def test_call_llm_routing_gemini_key(monkeypatch):
    called_urls = []

    def mock_post_json(url, payload, headers=None, timeout=45):
        called_urls.append(url)
        return {"choices": [{"message": {"content": "Gemini response"}}]}, None

    monkeypatch.setattr("control_plane.src.services.llm_service.post_json", mock_post_json)

    res, err = call_llm("hello", openai_key="AIzaSyDummyGeminiKey")
    assert err is None
    assert res == "Gemini response"
    assert any("generativelanguage.googleapis.com" in u for u in called_urls)
