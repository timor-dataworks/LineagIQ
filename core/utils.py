"""LineagIQ Core Utilities.

Shared timestamp parsing, text normalization, and search term extraction utilities.
"""

import re
import datetime
from typing import List, Optional

STOP_WORDS = {
    "find", "show", "search", "get", "list", "where", "is", "are", "the",
    "a", "an", "for", "with", "in", "me", "dataset", "datasets", "table",
    "tables", "column", "columns", "all", "what", "which", "who", "how", "tell", "about"
}


def parse_iso_to_epoch_ms(iso_str: Optional[str]) -> Optional[int]:
    """Parses ISO 8601 timestamp string into Epoch milliseconds.

    Args:
        iso_str: ISO 8601 string (e.g. '2026-09-08T10:00:00Z' or '2026-09-08T10:00:00.123Z').

    Returns:
        Epoch milliseconds int or None if invalid/empty.
    """
    if not iso_str:
        return None
    clean = iso_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(clean)
        epoch_ms = int(dt.timestamp() * 1000)
        if "." not in iso_str and "T" in iso_str:
            epoch_ms += 999
        return epoch_ms
    except Exception:
        return None


def extract_search_terms(query_text: str) -> List[str]:
    """Extracts and filters normalized search term phrases from a natural language query string.

    Args:
        query_text: Raw user query string.

    Returns:
        List of clean search term strings (minimum length 2).
    """
    raw_clean = query_text.lower().strip()
    words = [w for w in re.split(r'\s+', raw_clean) if w]
    filtered_words = [w for w in words if w not in STOP_WORDS]

    terms = []
    if filtered_words:
        terms.append(" ".join(filtered_words))
        for w in filtered_words:
            if w not in terms:
                terms.append(w)
    if raw_clean not in terms:
        terms.append(raw_clean)

    return [t for t in terms if len(t) >= 2]
