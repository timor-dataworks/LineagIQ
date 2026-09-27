import re


def clean_latex_to_unicode(text: str | None) -> str | None:
    """Sanitizes LaTeX math formatting from LLM responses into clean Unicode and plain text."""
    if not text:
        return text

    # Strip \text{...}, \mathrm{...}, \mathbf{...}, \mathit{...} wrappers
    text = re.sub(r"\\text\{([^}]+)\}", r"\1", text)
    text = re.sub(r"\\mathrm\{([^}]+)\}", r"\1", text)
    text = re.sub(r"\\mathbf\{([^}]+)\}", r"\1", text)
    text = re.sub(r"\\mathit\{([^}]+)\}", r"\1", text)

    # Convert escaped underscores often generated in LaTeX
    text = re.sub(r"\\_", "_", text)

    # Clean LaTeX arrows into clean Unicode
    text = re.sub(r"\$\s*\\+(?:rightarrow|to)\s*\$", "→", text)
    text = re.sub(r"\\+(?:rightarrow|to)\b", "→", text)
    text = re.sub(r"\$\s*\\+leftarrow\s*\$", "←", text)
    text = re.sub(r"\\+leftarrow\b", "←", text)
    text = re.sub(r"\$\s*\\+Rightarrow\s*\$", "⇒", text)
    text = re.sub(r"\\+Rightarrow\b", "⇒", text)
    text = re.sub(r"\$\s*\\+Leftarrow\s*\$", "⇐", text)
    text = re.sub(r"\\+Leftarrow\b", "⇐", text)
    text = re.sub(r"\$\s*\\+leftrightarrow\s*\$", "↔", text)
    text = re.sub(r"\\+leftrightarrow\b", "↔", text)
    text = re.sub(r"\$\s*\\+Leftrightarrow\s*\$", "⇔", text)
    text = re.sub(r"\\+Leftrightarrow\b", "⇔", text)
    text = re.sub(r"\$\s*\\+(?:longrightarrow|mapsto|implies)\s*\$", "⟶", text)
    text = re.sub(r"\\+(?:longrightarrow|mapsto|implies)\b", "⟶", text)

    # Common math symbols
    text = re.sub(r"\$\s*\\+approx\s*\$", "≈", text)
    text = re.sub(r"\\+approx\b", "≈", text)
    text = re.sub(r"\$\s*\\+neq\s*\$", "≠", text)
    text = re.sub(r"\\+neq\b", "≠", text)
    text = re.sub(r"\$\s*\\+(?:le|leq)\s*\$", "≤", text)
    text = re.sub(r"\\+(?:le|leq)\b", "≤", text)
    text = re.sub(r"\$\s*\\+(?:ge|geq)\s*\$", "≥", text)
    text = re.sub(r"\\+(?:ge|geq)\b", "≥", text)
    text = re.sub(r"\$\s*\\+times\s*\$", "×", text)
    text = re.sub(r"\\+times\b", "×", text)
    text = re.sub(r"\$\s*\\+cdot\s*\$", "·", text)
    text = re.sub(r"\\+cdot\b", "·", text)
    text = re.sub(r"\$\s*\\+(?:dots|cdots)\s*\$", "...", text)
    text = re.sub(r"\\+(?:dots|cdots)\b", "...", text)

    # Unwrap $...$ wrapping around arrow or simple math expressions
    text = re.sub(r"\$([^$\n]*?[→←⇒⇐↔⇔⟶⟵⟹↦][^$\n]*?)\$", r"\1", text)
    text = re.sub(r"\{([→←⇒⇐↔⇔⟶⟵⟹↦])\}", r"\1", text)

    return text
