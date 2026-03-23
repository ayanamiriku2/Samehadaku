import re
import json
import logging
from . import config

logger = logging.getLogger(__name__)

# All source domains to replace (v1, v2, bare domain, etc.)
_SOURCE_DOMAINS = [
    config.SOURCE_DOMAIN,  # v2.samehadaku.how
]

# Auto-detect related domains (v1, v3, etc.)
_domain_parts = config.SOURCE_DOMAIN.split(".", 1)
if len(_domain_parts) == 2 and _domain_parts[0].startswith("v"):
    _base = _domain_parts[1]
    for i in range(1, 10):
        variant = f"v{i}.{_base}"
        if variant not in _SOURCE_DOMAINS:
            _SOURCE_DOMAINS.append(variant)
    if _base not in _SOURCE_DOMAINS:
        _SOURCE_DOMAINS.append(_base)


def get_content_type(headers: dict) -> str:
    ct = headers.get("content-type", headers.get("Content-Type", ""))
    return ct.split(";")[0].strip().lower()


def is_html(content_type: str) -> bool:
    return content_type in ("text/html", "application/xhtml+xml")


def is_text_content(content_type: str) -> bool:
    """Check if content is text-based and should be rewritten."""
    text_types = (
        "text/html", "application/xhtml+xml",
        "text/css",
        "application/javascript", "text/javascript", "application/x-javascript",
        "application/json", "text/json",
        "text/xml", "application/xml", "application/rss+xml", "application/atom+xml",
        "text/plain",
        "application/manifest+json",
        "application/ld+json",
    )
    return content_type in text_types or "json" in content_type or "xml" in content_type


def _cf_decode(encoded: str) -> str:
    """Decode a Cloudflare cfemail hex string using XOR."""
    try:
        key = int(encoded[:2], 16)
        return "".join(chr(int(encoded[i:i+2], 16) ^ key) for i in range(2, len(encoded), 2))
    except (ValueError, IndexError):
        return ""


def _decode_cf_emails(html: str) -> str:
    """Replace CF email-protected <a> tags and <span> tags with decoded emails."""
    # Decode <a href="/cdn-cgi/l/email-protection" ... data-cfemail="...">
    def _replace_a(m):
        cfemail = m.group(1)
        decoded = _cf_decode(cfemail)
        if decoded:
            return f'<a href="mailto:{decoded}">{decoded}</a>'
        return m.group(0)

    html = re.sub(
        r'<a\s+href=["\'](?:/cdn-cgi/l/email-protection|[^"\']*cdn-cgi/l/email-protection)["\'][^>]*data-cfemail=["\']([0-9a-fA-F]+)["\'][^>]*>[^<]*</a>',
        _replace_a, html, flags=re.IGNORECASE,
    )
    # Decode standalone <span class="__cf_email__" data-cfemail="...">
    def _replace_span(m):
        cfemail = m.group(1)
        decoded = _cf_decode(cfemail)
        return decoded if decoded else m.group(0)

    html = re.sub(
        r'<span\s+class=["\']__cf_email__["\'][^>]*data-cfemail=["\']([0-9a-fA-F]+)["\'][^>]*/?>(?:\[email[^]]*\])?(?:</span>)?',
        _replace_span, html, flags=re.IGNORECASE,
    )
    return html


# --- Gambling / judi online ad removal ---

# Known gambling/spam ad domains (href targets)
_AD_DOMAINS = re.compile(
    r'(?:g66top\.me|tinig22\.com|slotjanji\.com|tokyo77[\w-]*\.com'
    r'|gacortokyo\.com|joiboy\.ink|royal22\.vip|viplinkzeus4d\.com'
    r'|klik\.gg|cek\.to|gacor\.vin|klik\.top|aksesin\.top'
    r'|tapme\.ink|server-x7\.xyz|tinyurl\.com|cutt\.ly'
    r'|slot[\w]*\.com|togel[\w]*\.com|judionline[\w]*\.com'
    r'|zeus4d|ketuaslot|arenaspin|momoplay|zipzap'
    r'|gacor|dewa66|mizu|zeon)',
    re.IGNORECASE,
)

# Pattern 1: <a href="AD_URL"><img style="width: 50%; height: 70px;" ...></a>
# These are the gambling banner ads with consistent 50%/70px sizing
# Also handles malformed HTML where </a> is missing
_AD_BANNER_RE = re.compile(
    r'<a\s+[^>]*href=["\'][^"\']*["\'][^>]*>'
    r'\s*<img\s+[^>]*style=["\'][^"\']*width:\s*50%;\s*height:\s*70px[^"\']*["\'][^>]*/?\s*>'
    r'\s*(?:</a>)?',
    re.IGNORECASE | re.DOTALL,
)

# Pattern 2: <a> tags linking to known gambling domains with images
_AD_LINK_IMG_RE = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>\s*<img\s+[^>]*/?\s*>\s*</a>',
    re.IGNORECASE | re.DOTALL,
)


def _remove_ad_banners(html: str) -> str:
    """Remove gambling/judi online ad banners and links."""
    # Remove all banner ads with the 50%/70px pattern
    html = _AD_BANNER_RE.sub('', html)

    # Remove remaining <a><img></a> that link to known gambling domains
    def _check_ad_link(m):
        href = m.group(1)
        if _AD_DOMAINS.search(href):
            return ''
        return m.group(0)

    html = _AD_LINK_IMG_RE.sub(_check_ad_link, html)

    # Remove player overlay ads (playerIklan divs)
    html = re.sub(
        r'<div\s+[^>]*id=["\']playerIklan\d*["\'][^>]*>.*?</div>',
        '', html, flags=re.IGNORECASE | re.DOTALL,
    )

    # Remove playerIklan JS functions
    html = re.sub(
        r'function\s+playerIklan\w+\([^)]*\)\s*\{[^}]*\}',
        '', html, flags=re.DOTALL,
    )

    # Remove playerIklan.remove() calls
    html = re.sub(
        r"document\.getElementById\(['\"]playerIklan\d*['\"]\)\.remove\(\);",
        '', html,
    )

    # Clean up leftover blank lines from removed ads
    html = re.sub(r'\n{3,}', '\n\n', html)

    return html


def _replace_all_domains(text: str, mirror_url: str = "", mirror_domain: str = "", mirror_scheme: str = "") -> str:
    """Replace all source domain references with mirror domain (pure string ops)."""
    m_url = mirror_url or config.MIRROR_URL
    m_domain = mirror_domain or config.MIRROR_DOMAIN
    m_scheme = mirror_scheme or config.MIRROR_SCHEME
    for domain in _SOURCE_DOMAINS:
        text = text.replace(f"https://{domain}", m_url)
        text = text.replace(f"http://{domain}", m_url)
        text = text.replace(f"//{domain}", f"//{m_domain}")
        # Escaped versions (common in JSON/JS)
        text = text.replace(
            f"https:\\/\\/{domain}",
            f"{m_scheme}:\\/\\/{m_domain}",
        )
        text = text.replace(
            f"http:\\/\\/{domain}",
            f"{m_scheme}:\\/\\/{m_domain}",
        )
        # URL-encoded dots
        encoded_d = domain.replace(".", "%2E")
        encoded_m = m_domain.replace(".", "%2E")
        text = text.replace(encoded_d, encoded_m)
    return text


def rewrite_html(html: str, request_path: str,
                 mirror_url: str = "", mirror_domain: str = "", mirror_scheme: str = "") -> str:
    """
    Rewrite HTML using regex (NOT BeautifulSoup) to preserve HTML integrity.
    BeautifulSoup corrupts complex HTML - using pure regex is more reliable.
    """
    m_url = mirror_url or config.MIRROR_URL

    # Step 1: Replace all domain references
    html = _replace_all_domains(html, mirror_url=mirror_url, mirror_domain=mirror_domain, mirror_scheme=mirror_scheme)

    # Step 2: Fix canonical tag - force it to point to our mirror path
    canonical_re = re.compile(
        r'<link\s+[^>]*rel=["\']canonical["\'][^>]*/?>',
        re.IGNORECASE,
    )
    canonical_match = canonical_re.search(html)
    new_canonical = f'<link rel="canonical" href="{m_url}{request_path}" />'
    if canonical_match:
        html = canonical_re.sub(new_canonical, html, count=1)
    else:
        # Insert after <head...>
        head_re = re.compile(r'(<head[^>]*>)', re.IGNORECASE)
        head_match = head_re.search(html)
        if head_match:
            pos = head_match.end()
            html = html[:pos] + "\n" + new_canonical + html[pos:]

    # Step 3: Fix og:url
    og_re1 = re.compile(
        r'(<meta\s+[^>]*property=["\']og:url["\'][^>]*content=["\'])([^"\']+)(["\'])',
        re.IGNORECASE,
    )
    html = og_re1.sub(rf'\g<1>{m_url}{request_path}\g<3>', html)
    og_re2 = re.compile(
        r'(<meta\s+[^>]*content=["\'])([^"\']+)(["\'][^>]*property=["\']og:url["\'])',
        re.IGNORECASE,
    )
    html = og_re2.sub(rf'\g<1>{m_url}{request_path}\g<3>', html)

    # Step 4: Remove google-site-verification (mirror owner adds their own)
    html = re.sub(
        r'<meta\s+[^>]*name=["\']google-site-verification["\'][^>]*/?>',
        '', html, flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<meta\s+[^>]*name=["\']msvalidate\.01["\'][^>]*/?>',
        '', html, flags=re.IGNORECASE,
    )

    # Step 5: Remove Cloudflare challenge scripts & iframe injector
    # These are injected by CF and break the page on the mirror
    # Remove inline script that creates the challenge iframe
    html = re.sub(
        r'<script>\(function\(\)\{function c\(\).*?challenge-platform.*?</script>',
        '', html, flags=re.DOTALL,
    )
    # Remove any <script> tags loading from /cdn-cgi/
    html = re.sub(
        r'<script[^>]*src=["\'][^"\']*/cdn-cgi/[^"\']*["\'][^>]*>(?:</script>)?',
        '', html, flags=re.IGNORECASE,
    )
    # Remove noscript blocks related to CF challenge
    html = re.sub(
        r'<noscript[^>]*>.*?challenge.*?</noscript>',
        '', html, flags=re.DOTALL | re.IGNORECASE,
    )
    # Remove CF __cf_chl script vars
    html = re.sub(
        r'<script[^>]*>\s*window\.__CF\$cv\$params.*?</script>',
        '', html, flags=re.DOTALL,
    )
    # Remove CF Rocket Loader
    html = re.sub(
        r'<script[^>]*src=["\'][^"\']*/cdn-cgi/scripts/[^"\']["\'][^>]*/?>(?:</script>)?',
        '', html, flags=re.IGNORECASE,
    )
    # Remove CF email obfuscation scripts
    html = re.sub(
        r'<script[^>]*data-cfasync=["\']false["\'][^>]*src=["\'][^"\']*/cdn-cgi/[^"\']*["\'][^>]*>(?:</script>)?',
        '', html, flags=re.IGNORECASE,
    )

    # Step 6: Decode Cloudflare email-protected addresses inline
    html = _decode_cf_emails(html)

    # Step 7: Remove gambling/judi online ad banners & links
    html = _remove_ad_banners(html)

    # Step 8: Remove "PENTING" announcement widget
    html = re.sub(
        r'<div\s+class=["\']widget_senction["\']>.*?</div>\s*\n?\s*'
        r'(?:<!--\s*/wp:group\s*-->\s*</div>)?',
        '', html, flags=re.DOTALL | re.IGNORECASE,
    )

    # Step 9: Fix structured data (JSON-LD)
    html = _fix_structured_data(html, request_path, m_url)

    return html


def _fix_structured_data(html: str, request_path: str, mirror_url: str) -> str:
    """Fix JSON-LD structured data: remove junk, inject breadcrumbs if missing."""
    has_yoast_breadcrumb = False

    def _process_ld_block(m):
        nonlocal has_yoast_breadcrumb
        raw = m.group(1)
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return m.group(0)

        # Remove linktree ProfilePage JSON-LD (invalid @id, SEO junk)
        if data.get("@type") == "ProfilePage" and "linktr" in str(data.get("isPartOf", "")):
            return ""

        # Check if Yoast @graph already has BreadcrumbList
        if "@graph" in data:
            for item in data["@graph"]:
                if item.get("@type") == "BreadcrumbList":
                    has_yoast_breadcrumb = True
                    break

        return m.group(0)

    html = re.sub(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        _process_ld_block, html, flags=re.DOTALL | re.IGNORECASE,
    )

    # Inject breadcrumb JSON-LD for pages that lack Yoast schema
    if not has_yoast_breadcrumb and request_path != "/":
        # Extract page title for breadcrumb name
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        page_name = ""
        if title_match:
            raw_title = title_match.group(1).strip()
            # Skip junk titles (linktree etc.)
            if not re.search(r'linktree|linktr\.ee', raw_title, re.IGNORECASE):
                page_name = raw_title.split(" - ")[0].split(" | ")[0].strip()

        # Fall back to deriving name from URL path
        if not page_name:
            slug = request_path.strip("/").split("/")[-1]
            page_name = slug.replace("-", " ").title()

        breadcrumb_ld = json.dumps({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Beranda",
                    "item": mirror_url + "/",
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": page_name,
                },
            ],
        }, ensure_ascii=False)

        # Insert before </head>
        html = re.sub(
            r'(</head>)',
            f'<script type="application/ld+json">{breadcrumb_ld}</script>\n\\1',
            html, count=1, flags=re.IGNORECASE,
        )

    return html


def rewrite_body(body: bytes, content_type: str, request_path: str,
                 mirror_url: str = "", mirror_domain: str = "", mirror_scheme: str = "") -> bytes:
    """Main entry point: rewrite response body based on content type."""
    if not is_text_content(content_type):
        return body

    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return body

    if is_html(content_type):
        text = rewrite_html(text, request_path, mirror_url=mirror_url, mirror_domain=mirror_domain, mirror_scheme=mirror_scheme)
    else:
        text = _replace_all_domains(text, mirror_url=mirror_url, mirror_domain=mirror_domain, mirror_scheme=mirror_scheme)

    return text.encode("utf-8")


def rewrite_headers(headers: dict, mirror_url: str = "", mirror_domain: str = "") -> dict:
    """Rewrite response headers, removing problematic ones and fixing redirects."""
    remove_headers = {
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "strict-transport-security",
        "content-security-policy",
        "content-security-policy-report-only",
        "x-frame-options",
        "set-cookie",
        "alt-svc",
        "cf-ray",
        "cf-cache-status",
        "cf-request-id",
        "server",
        "expect-ct",
        "report-to",
        "nel",
    }

    result = {}
    m_url = mirror_url or config.MIRROR_URL
    m_domain = mirror_domain or config.MIRROR_DOMAIN
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in remove_headers:
            continue
        if lower_key.startswith("cf-"):
            continue

        if lower_key in ("location", "link", "content-location"):
            for domain in _SOURCE_DOMAINS:
                value = value.replace(f"https://{domain}", m_url)
                value = value.replace(f"http://{domain}", m_url)
                value = value.replace(f"//{domain}", f"//{m_domain}")

        result[key] = value

    return result
