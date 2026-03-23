import random
import logging
from curl_cffi import requests as cf_requests
from . import config

logger = logging.getLogger(__name__)

# Persistent session for connection reuse
_session = None


def get_session() -> cf_requests.Session:
    """Get or create a persistent curl_cffi session."""
    global _session
    if _session is None:
        _session = cf_requests.Session(
            impersonate=config.IMPERSONATE_BROWSER,
            timeout=config.REQUEST_TIMEOUT,
        )
    return _session


def fetch_from_source(
    path: str,
    method: str = "GET",
    headers: dict | None = None,
    body: bytes | None = None,
    query_string: str = "",
) -> tuple[int, dict, bytes]:
    """
    Fetch a resource from the source website using curl_cffi
    which impersonates a real browser's TLS fingerprint to bypass Cloudflare.

    Returns: (status_code, response_headers_dict, response_body_bytes)
    """
    url = f"{config.SOURCE_URL}{path}"
    if query_string:
        url = f"{url}?{query_string}"

    # Build request headers
    req_headers = {
        "User-Agent": random.choice(config.USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": config.SOURCE_URL + "/",
        "DNT": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

    # Merge incoming headers (but keep our important ones)
    if headers:
        pass_through = {
            "accept", "accept-language", "content-type",
            "x-requested-with", "range", "if-none-match",
            "if-modified-since",
        }
        for key, value in headers.items():
            if key.lower() in pass_through:
                req_headers[key] = value

    # Always override Host to source
    req_headers["Host"] = config.SOURCE_DOMAIN

    # Remove headers that would identify the mirror
    for h in ["x-forwarded-for", "x-real-ip", "x-forwarded-host", "cf-connecting-ip"]:
        req_headers.pop(h, None)

    session = get_session()

    try:
        if method.upper() == "GET":
            response = session.get(url, headers=req_headers, allow_redirects=False)
        elif method.upper() == "POST":
            response = session.post(url, headers=req_headers, data=body, allow_redirects=False)
        elif method.upper() == "HEAD":
            response = session.head(url, headers=req_headers, allow_redirects=False)
        elif method.upper() == "OPTIONS":
            response = session.options(url, headers=req_headers, allow_redirects=False)
        elif method.upper() == "PUT":
            response = session.put(url, headers=req_headers, data=body, allow_redirects=False)
        elif method.upper() == "DELETE":
            response = session.delete(url, headers=req_headers, allow_redirects=False)
        elif method.upper() == "PATCH":
            response = session.patch(url, headers=req_headers, data=body, allow_redirects=False)
        else:
            response = session.get(url, headers=req_headers, allow_redirects=False)

        resp_headers = dict(response.headers)
        return response.status_code, resp_headers, response.content

    except Exception as e:
        logger.error(f"Fetch error for {url}: {e}")
        # Reset session on error
        reset_session()
        raise


def reset_session():
    """Reset the session (useful after errors)."""
    global _session
    _session = None
