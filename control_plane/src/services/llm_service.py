import os

from control_plane.src.services.http_client import post_json
from control_plane.src.services.latex_sanitizer import clean_latex_to_unicode


def call_openai_llm(
    prompt: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> tuple[str | None, str | None]:
    """Calls OpenAI API or OpenAI-compatible provider (Azure, Ollama, vLLM, Groq, OpenRouter).

    Automatically routes Gemini API keys (AIza..., AQ...) to Google's OpenAI endpoint
    if no custom base_url is set.

    Args:
        prompt: Full prompt string to submit to LLM.
        api_key: Optional API key override.
        base_url: Optional API base URL endpoint override.
        model: Optional LLM model identifier override.

    Returns:
        Tuple of (generated_response_text, error_message_string).
    """
    key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    endpoint = (base_url or os.getenv("OPENAI_BASE_URL") or "").rstrip("/")

    # Allow local Ollama or local LLM servers without requiring API key
    if not key:
        if endpoint and any(h in endpoint.lower() for h in ["11434", "localhost", "127.0.0.1", "ollama"]):
            key = "ollama"
        else:
            return None, None

    is_gemini_key = (
        key.startswith("AIza") or key.startswith("AQ") or (not key.startswith("sk-") and key != "ollama")
    ) and not (endpoint and "11434" in endpoint)
    default_base_url = (
        "https://generativelanguage.googleapis.com/v1beta/openai" if is_gemini_key else "https://api.openai.com/v1"
    )
    default_model = "gemini-3.6-flash" if is_gemini_key else ("llama3" if key == "ollama" else "gpt-4o-mini")

    if not endpoint:
        endpoint = default_base_url
    elif "11434" in endpoint and not endpoint.endswith("/v1"):
        endpoint = f"{endpoint}/v1"

    url = f"{endpoint}/chat/completions"
    model_name = model or os.getenv("OPENAI_MODEL") or default_model

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are LineagIQ AI Assistant, an expert data lineage, governance, and blast radius reasoning agent.\n"
                    "CRITICAL FORMATTING INSTRUCTION: Format your responses using clean, semantic HTML tags "
                    "(e.g. <p>, <strong>, <code>, <ul>, <li>, <em>, <br>). Do NOT use Markdown formatting and do NOT use LaTeX math formatting. "
                    "Use standard Unicode arrows (such as '→' for lineage transitions, '←', '⇒')."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    body, err = post_json(url, payload, headers={"Authorization": f"Bearer {key}"})
    if body and isinstance(body, dict):
        choices = body.get("choices", [])
        if choices and isinstance(choices, list) and len(choices) > 0:
            content = choices[0].get("message", {}).get("content")
            if content:
                return clean_latex_to_unicode(content), None

    return None, err


def call_gemini_llm(prompt: str, api_key: str | None = None) -> tuple[str | None, str | None]:
    """Calls Google Gemini API (gemini-3.6-flash) using standard REST HTTP endpoint.

    Args:
        prompt: Full prompt string to submit to Gemini.
        api_key: Optional Gemini/Google API key override.

    Returns:
        Tuple of (generated_response_text, error_message_string).
    """
    key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None, None

    formatting_rule = (
        "\n\nCRITICAL FORMATTING INSTRUCTION: Format your response using clean, semantic HTML tags "
        "(e.g. <p>, <strong>, <code>, <ul>, <li>, <em>, <br>). Do NOT use Markdown or LaTeX. Use Unicode arrows ('→').\n"
    )
    payload = {"contents": [{"parts": [{"text": prompt + formatting_rule}]}]}
    last_err = None

    for model_name in ["gemini-3.6-flash"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        body, err = post_json(url, payload)
        if body and isinstance(body, dict):
            candidates = body.get("candidates", [])
            if candidates and isinstance(candidates, list) and len(candidates) > 0:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and parts[0].get("text"):
                    return clean_latex_to_unicode(parts[0]["text"]), None
        if err:
            last_err = err

    return None, last_err


def call_llm(
    prompt: str,
    openai_key: str | None = None,
    openai_base_url: str | None = None,
    openai_model: str | None = None,
) -> tuple[str | None, str | None]:
    """Attempts to generate LLM response using configured providers in order:
    1. OpenAI / OpenAI-compatible API (including Gemini AIza keys via Google OpenAI endpoint)
    2. Google Gemini Native API

    Args:
        prompt: Full prompt string for LLM completion.
        openai_key: Optional OpenAI API key override.
        openai_base_url: Optional base URL endpoint override.
        openai_model: Optional model name override.

    Returns:
        Tuple of (generated_response_text, error_message_string).
    """
    openai_res, openai_err = call_openai_llm(prompt, api_key=openai_key, base_url=openai_base_url, model=openai_model)
    if openai_res:
        return clean_latex_to_unicode(openai_res), None

    gemini_res, gemini_err = call_gemini_llm(prompt, api_key=openai_key)
    if gemini_res:
        return clean_latex_to_unicode(gemini_res), None

    return None, openai_err or gemini_err
