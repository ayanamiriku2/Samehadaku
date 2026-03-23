import os

# Source website to mirror
SOURCE_DOMAIN = os.getenv("SOURCE_DOMAIN", "v2.samehadaku.how")
SOURCE_SCHEME = os.getenv("SOURCE_SCHEME", "https")
SOURCE_URL = f"{SOURCE_SCHEME}://{SOURCE_DOMAIN}"

# Your mirror domain (set this to your actual deployed domain)
MIRROR_DOMAIN = os.getenv("MIRROR_DOMAIN", "samehadaku.ink")
MIRROR_SCHEME = os.getenv("MIRROR_SCHEME", "https")
MIRROR_URL = f"{MIRROR_SCHEME}://{MIRROR_DOMAIN}"

# Cache settings
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_DIR = os.getenv("CACHE_DIR", "/tmp/mirror_cache")
CACHE_TTL_HTML = int(os.getenv("CACHE_TTL_HTML", "300"))       # 5 minutes for HTML
CACHE_TTL_ASSETS = int(os.getenv("CACHE_TTL_ASSETS", "86400")) # 24 hours for assets
CACHE_TTL_API = int(os.getenv("CACHE_TTL_API", "60"))          # 1 minute for API

# Server settings
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
WORKERS = int(os.getenv("WORKERS", "4"))

# curl_cffi impersonate browser
IMPERSONATE_BROWSER = os.getenv("IMPERSONATE_BROWSER", "chrome")

# Request timeout in seconds
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# User agent rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Paths to exclude from mirroring (admin, login, etc.)
EXCLUDED_PATHS = [
    "/wp-admin",
    "/wp-login.php",
    "/xmlrpc.php",
]

# Custom meta tags to inject for SEO
CUSTOM_META_DESCRIPTION = os.getenv("CUSTOM_META_DESCRIPTION", "")
CUSTOM_SITE_TITLE_SUFFIX = os.getenv("CUSTOM_SITE_TITLE_SUFFIX", "")
