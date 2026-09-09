import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


def post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 45,
) -> Tuple[Optional[Any], Optional[str]]:
    """Generic JSON POST request helper using standard urllib.

    Args:
        url: Target HTTP endpoint URL.
        payload: Data dictionary to serialize as JSON payload.
        headers: Optional HTTP headers dictionary.
        timeout: HTTP request timeout in seconds. Defaults to 45.

    Returns:
        Tuple of (parsed_json_response_dict, error_message_string).
        On success, second element is None. On failure, first element is None.
    """
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        err_text = ""
        try:
            err_text = e.read().decode("utf-8")
        except Exception:
            pass
        msg = f"HTTP {e.code}"
        if err_text:
            try:
                parsed = json.loads(err_text)
                if isinstance(parsed, dict) and "error" in parsed:
                    err_obj = parsed["error"]
                    if isinstance(err_obj, dict) and "message" in err_obj:
                        msg += f": {err_obj['message']}"
                    else:
                        msg += f": {err_obj}"
                elif isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict) and "error" in parsed[0]:
                    msg += f": {parsed[0]['error'].get('message', parsed[0]['error'])}"
                else:
                    msg += f": {err_text[:200]}"
            except Exception:
                msg += f": {err_text[:200]}"
        logger.warning(f"HTTP Error for POST {url}: {msg}")
        return None, msg
    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower():
            err_msg = f"Request timed out ({timeout}s limit exceeded)"
        logger.warning(f"HTTP POST request warning to {url}: {err_msg}")
        return None, err_msg
