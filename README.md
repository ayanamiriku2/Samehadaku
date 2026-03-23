# Samehadaku Mirror Proxy

Full mirror reverse proxy untuk `v2.samehadaku.how` dengan **Cloudflare bypass** dan **anti-duplikat SEO**.

## Fitur

- **Cloudflare Bypass** — Menggunakan `curl_cffi` dengan TLS fingerprint browser asli (bukan Puppeteer, tanpa headless browser)
- **Anti-Duplikat SEO** — Semua URL di-rewrite ke domain mirror, canonical tag diset ke mirror, og:url difix, google-site-verification dihapus
- **Full Mirror** — HTML, CSS, JS, JSON, XML, sitemap, RSS feed — semua domain references di-replace
- **Multi-domain Support** — Otomatis detect dan replace v1, v2, v3...v9 variants
- **Cache Layer** — File-based cache untuk HTML (5 menit) dan assets (24 jam)
- **Deploy Anywhere** — Railway, Render, EasyPanel, VPS, Docker

## Quick Start

### Docker (Recommended)

```bash
# Edit docker-compose.yml — ganti MIRROR_DOMAIN dengan domain kamu
docker compose up -d
```

### VPS (Tanpa Docker)

```bash
# Install Python 3.12+
sudo apt update && sudo apt install -y python3 python3-pip python3-venv

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Konfigurasi
cp .env.example .env
# Edit .env — WAJIB isi MIRROR_DOMAIN dengan domain kamu

# Jalankan
bash start.sh
```

### Railway

1. Push repo ke GitHub
2. Connect repo di Railway
3. Set environment variables:
   - `MIRROR_DOMAIN` = domain Railway kamu (misal: `xxx.up.railway.app`)
   - `MIRROR_SCHEME` = `https`
4. Deploy otomatis dari `railway.json`

### Render

1. Push repo ke GitHub
2. New Web Service → connect repo
3. Set `MIRROR_DOMAIN` di environment variables
4. Deploy otomatis dari `render.yaml`

### EasyPanel

1. Create new project di EasyPanel
2. Add service → Docker → point ke repo
3. Set environment `MIRROR_DOMAIN` ke domain EasyPanel kamu
4. Config ada di `easypanel.json`

## Environment Variables

| Variable | Default | Keterangan |
|---|---|---|
| `SOURCE_DOMAIN` | `v2.samehadaku.how` | Domain sumber yang di-mirror |
| `MIRROR_DOMAIN` | `localhost:8000` | **WAJIB DIISI** — domain mirror kamu |
| `MIRROR_SCHEME` | `https` | `http` atau `https` |
| `CACHE_ENABLED` | `true` | Aktifkan cache |
| `CACHE_TTL_HTML` | `300` | Cache TTL HTML (detik) |
| `CACHE_TTL_ASSETS` | `86400` | Cache TTL assets (detik) |
| `WORKERS` | `4` | Jumlah worker uvicorn |
| `IMPERSONATE_BROWSER` | `chrome` | Browser fingerprint (`chrome`, `safari`, `edge`) |

## Anti-Duplikat SEO — Cara Kerja

Masalah utama mirror website di Google Search Console adalah **duplikat konten**. Proxy ini menyelesaikannya dengan:

1. **Canonical Tag** — Setiap halaman HTML mendapat `<link rel="canonical">` yang mengarah ke domain mirror, bukan domain asli
2. **OG:URL** — Meta tag `og:url` di-rewrite ke domain mirror
3. **Domain Replacement** — SEMUA referensi domain asli (v1, v2, dll) di-replace ke domain mirror di HTML, CSS, JS, JSON, XML, sitemap
4. **Verification Removal** — Tag `google-site-verification` dan `msvalidate.01` dari situs asli dihapus (kamu pasang sendiri yang baru)
5. **Sitemap Rewrite** — Sitemap XML otomatis ter-rewrite dengan URL mirror
6. **Custom Robots.txt** — Robots.txt khusus dengan sitemap pointing ke mirror
7. **X-Robots-Tag** — Header `X-Robots-Tag: index, follow` ditambahkan

## Endpoints

| Path | Fungsi |
|---|---|
| `/_health` | Health check |
| `/_cache/clear` | Clear cache (POST) |
| `/robots.txt` | Custom robots.txt |
| `/*` | Mirror proxy |

## Tech Stack

- **Python 3.12** + **FastAPI** + **uvicorn**
- **curl_cffi** — HTTP client dengan TLS fingerprinting (bypass Cloudflare tanpa browser)
- **Regex-based HTML rewriting** — Lebih reliable dari BeautifulSoup (tidak merusak HTML structure)
