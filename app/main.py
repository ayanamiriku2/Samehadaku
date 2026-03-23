import logging
import time
from urllib.parse import urlparse
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, RedirectResponse
from . import config
from .proxy import fetch_from_source
from .rewriter import (
    rewrite_body,
    rewrite_headers,
    get_content_type,
    is_html,
    _replace_all_domains,
)
from .cache import cache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mirror Proxy",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _detect_mirror(request: Request) -> tuple[str, str, str]:
    """Auto-detect mirror scheme, domain, and URL from the incoming request.
    Works behind reverse proxies (Codespaces, Railway, Render, Nginx, etc.)."""
    # Detect scheme
    scheme = (
        request.headers.get("x-forwarded-proto")
        or request.headers.get("x-scheme")
        or str(request.url.scheme)
    ).split(",")[0].strip()

    # Detect host
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or config.MIRROR_DOMAIN
    ).split(",")[0].strip()

    # Remove default ports
    if (scheme == "https" and host.endswith(":443")):
        host = host[:-4]
    elif (scheme == "http" and host.endswith(":80")):
        host = host[:-3]

    url = f"{scheme}://{host}"
    return scheme, host, url


# ── Health check ──────────────────────────────────────────────

@app.get("/_health")
async def health():
    return {"status": "ok", "source": config.SOURCE_DOMAIN, "mirror": config.MIRROR_DOMAIN}


# ── Block Cloudflare internal paths ──────────────────────────

@app.api_route("/cdn-cgi/{path:path}", methods=["GET", "POST", "HEAD", "OPTIONS"])
async def block_cdn_cgi(path: str):
    return PlainTextResponse("", status_code=204)


# ── Custom robots.txt ────────────────────────────────────────

@app.get("/robots.txt")
async def robots_txt(request: Request):
    _, _, mirror_url = _detect_mirror(request)
    content = f"""User-agent: *
Allow: /
Disallow: /wp-admin/
Disallow: /wp-login.php
Disallow: /xmlrpc.php
Disallow: /_health

Sitemap: {mirror_url}/sitemap.xml
"""
    return PlainTextResponse(content, media_type="text/plain")


# ── Cache management ─────────────────────────────────────────

@app.post("/_cache/clear")
async def clear_cache():
    cache.clear()
    return {"status": "cache cleared"}


# ── Main reverse proxy catch-all ─────────────────────────────

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
@app.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_handler(request: Request):
    path = request.url.path
    query_string = str(request.query_params) if request.query_params else ""

    # Auto-detect mirror URL from request headers
    mirror_scheme, mirror_domain, mirror_url = _detect_mirror(request)

    # Block excluded paths
    for excluded in config.EXCLUDED_PATHS:
        if path.startswith(excluded):
            return PlainTextResponse("Not Found", status_code=404)

    # Build cache key (include host to avoid cross-domain cache mixing)
    cache_key = f"{mirror_domain}:{request.method}:{path}"
    if query_string:
        cache_key += f"?{query_string}"

    # Determine cache TTL based on content type hint from path
    cache_ttl = _get_cache_ttl(path)

    # Check cache first (only for GET requests)
    if request.method == "GET":
        cached = cache.get(cache_key, cache_ttl)
        if cached is not None:
            meta, body = cached
            return Response(
                content=body,
                status_code=meta.get("status_code", 200),
                headers=meta.get("headers", {}),
            )

    # Read request body for non-GET methods
    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        body = await request.body()

    # Build forwarded headers
    incoming_headers = dict(request.headers)

    try:
        start = time.time()
        status_code, resp_headers, resp_body = fetch_from_source(
            path=path,
            method=request.method,
            headers=incoming_headers,
            body=body,
            query_string=query_string,
        )
        elapsed = time.time() - start
        logger.info(f"{request.method} {path} -> {status_code} ({elapsed:.2f}s, {len(resp_body)} bytes)")
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return PlainTextResponse("Bad Gateway", status_code=502)

    # Handle redirects - rewrite Location header
    if status_code in (301, 302, 303, 307, 308):
        location = resp_headers.get("location", resp_headers.get("Location", ""))
        if location:
            location = _replace_all_domains(location, mirror_url=mirror_url, mirror_domain=mirror_domain, mirror_scheme=mirror_scheme)
            # If relative or absolute path, make sure it's on our domain
            if location.startswith("/"):
                location = f"{mirror_url}{location}"
            return RedirectResponse(url=location, status_code=status_code)

    # Rewrite headers
    clean_headers = rewrite_headers(resp_headers, mirror_url=mirror_url, mirror_domain=mirror_domain)

    # Determine content type
    content_type = get_content_type(resp_headers)

    # Rewrite body content
    rewritten_body = rewrite_body(resp_body, content_type, path,
                                  mirror_url=mirror_url, mirror_domain=mirror_domain, mirror_scheme=mirror_scheme)

    # Update content-length
    clean_headers["content-length"] = str(len(rewritten_body))

    # Add cache-control for assets
    if not is_html(content_type) and status_code == 200:
        clean_headers["cache-control"] = "public, max-age=86400"
    elif is_html(content_type):
        clean_headers["cache-control"] = "public, max-age=300, s-maxage=300"

    # Add X-Robots-Tag to help with indexing
    if is_html(content_type):
        clean_headers["x-robots-tag"] = "index, follow"

    # Store in cache (only successful GET responses)
    if request.method == "GET" and status_code == 200:
        cache_meta = {
            "status_code": status_code,
            "headers": clean_headers,
        }
        cache.set(cache_key, cache_meta, rewritten_body)

    return Response(
        content=rewritten_body,
        status_code=status_code,
        headers=clean_headers,
    )


def _get_cache_ttl(path: str) -> int:
    """Determine cache TTL based on path/extension."""
    lower = path.lower()
    asset_extensions = (
        ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg",
        ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".eot",
        ".mp4", ".webm", ".mp3", ".pdf",
    )
    if any(lower.endswith(ext) for ext in asset_extensions):
        return config.CACHE_TTL_ASSETS
    if "/wp-json/" in lower or "/api/" in lower:
        return config.CACHE_TTL_API
    return config.CACHE_TTL_HTML
