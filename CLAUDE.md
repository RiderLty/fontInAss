# CLAUDE.md — FontInAss

## Project Overview

FontInAss is a tool that **subsets fonts and embeds them into ASS/SSA/SRT subtitle files** in real-time. It solves the problem of subtitles not displaying correctly on devices that lack the required fonts by embedding a minimal subset of each font directly into the subtitle file using UUEncode.

Designed to work as a **transparent proxy** for Emby/Jellyfin media servers — intercepts subtitle requests, processes them with embedded fonts, and returns the modified subtitle to the client.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Nginx (port 8012) - reverse proxy for Emby/Jellyfin   │
│  Intercepts /videos/*/Subtitles/* requests              │
│  Proxies subtitle requests → Python service (8011)      │
│  Proxies all other requests → Emby server               │
│  Proxies JS files → Python for web font rendering hack  │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│  Python FastAPI service (port 8011)                     │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │ SubSetter   │ │ FontManager  │ │ dirmonitor       │ │
│  │ (subset +   │ │ (DB + cache  │ │ (watchdog on     │ │
│  │  embed)     │ │  + download) │ │  font dirs)      │ │
│  └──────┬──────┘ └──────┬───────┘ └────────┬─────────┘ │
│         │               │                  │            │
│  ┌──────▼───────────────▼──────────────────▼─────────┐  │
│  │          SQLite DB (localFonts.ver.2.6.db)        │  │
│  │          + TTL/LRU Caches (font + subtitle)       │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Cython/C++ extension (py2cy/c_utils)             │   │
│  │ - uuencode: UU-encode font binary for ASS embed  │   │
│  │ - analyseAss: Parse ASS to extract font→unicode   │   │
│  │ - parse_table: Parse OS/2 and head font tables   │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Vue 3 Frontend (/subset) - Batch subtitle tool   │   │
│  │ Vite + Ant Design Vue + vue-i18n                  │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Key Commands

### Build Cython Extension (required first)
```bash
python src/py2cy/setup.py
```

### Build Frontend
```bash
cd src/subset && npm install && npm run build
```

### Install Python Dependencies
```bash
# Using uv (recommended)
uv sync

# Using pip
pip install -r requirements.txt
```

### Run Locally
```bash
export EMBY_SERVER_URL="http://[ip]:[port]"
python src/main.py

# Or with uv
uv run src/main.py
```

### Run with Docker
```bash
docker run -d --name=fontinass --restart=unless-stopped \
  -p 8011:8011 -p 8012:8012 \
  -e EMBY_SERVER_URL=http://[ip]:[port] \
  -v /yourDir/fontinass/data:/data \
  -v /yourDir/fontinass/fonts:/fonts \
  riderlty/fontinass:latest
```

### Docker Build
```bash
# One-step build (all stages in Dockerfile)
docker build . -f Dockerfile -t riderlty/fontinass:latest

# Multi-stage: build builder image first
docker build . -f Dockerfile-builder -t riderlty/fontinass-builder:latest
# Then build noproxy
docker build . -f Dockerfile-noproxy -t riderlty/fontinass:noproxy
# Then build default (adds nginx)
docker build . -f Dockerfile-default -t riderlty/fontinass:latest
```

## Project Structure

```
fontInAss/
├── src/
│   ├── main.py              # FastAPI app entry point, HTTP endpoints
│   ├── constants.py          # All env vars, paths, config constants
│   ├── fontmanager.py        # Font DB (SQLAlchemy/SQLite), font loading, online download
│   ├── subsetter.py          # Core logic: ASS analysis → font subset → embed
│   ├── utils.py              # SRT→ASS conversion, font scoring, ASS manipulation
│   ├── analyseAss.py         # Pure Python ASS parser (backup, mostly replaced by C++)
│   ├── dirmonitor.py         # Watchdog-based font directory monitor
│   ├── colorAdjust.py        # HSV color adjustment for HDR subtitles
│   ├── logs.py               # Async log file manager for missing font/glyph logs
│   ├── docker.init.py        # Docker entrypoint: generates nginx config from env vars
│   ├── create_onlineFonts.json.py  # Utility to generate custom font online DB
│   ├── html/color.html       # Web UI for color/brightness adjustment
│   ├── py2cy/                # Cython/C++ performance-critical code
│   │   ├── c_utils.pyx       # uuencode, analyseAss (C++ impl), parse_table
│   │   ├── cpp_utils.cpp     # C++ ASS analysis implementation
│   │   └── setup.py          # Cython build script
│   └── subset/               # Vue 3 frontend for batch subtitle processing
│       ├── package.json      # Node.js dependencies (vue, ant-design-vue, vite)
│       ├── vite.config.js    # Vite config
│       └── src/
│           ├── main.js       # Vue app with i18n (zh-CN, en-US)
│           ├── App.vue       # Root component
│           └── components/
│               └── subset.vue  # Main batch processing UI
├── nginx/
│   ├── nginx.conf            # Nginx main config
│   └── conf.d/emby.conf.template  # Emby proxy config template
├── onlineFonts.json          # Pre-built online font database (~10MB)
├── fonts/                    # Local font files directory
│   └── download/             # Auto-downloaded fonts from CDN
├── data/                     # Runtime data (mounted volume)
│   ├── localFonts.ver.2.6.db # SQLite font database
│   └── customOnlineFonts.json  # Optional custom online font DB
├── test/                     # Test ASS subtitle files
├── Dockerfile                # One-step build (all stages inline)
├── Dockerfile-builder        # Builder image (Cython + Node.js build)
├── Dockerfile-noproxy        # Runtime image without nginx
├── Dockerfile-default        # Adds nginx to noproxy image
├── pyproject.toml            # Python project config (uv/pip)
├── requirements.txt          # Python dependencies
├── .python-version           # 3.10.16
├── run.sh                    # Container entrypoint
├── debug.sh                  # Development/debug helper
├── subset.py                 # CLI tool for batch processing via API
├── checkTool.py              # Test script for checking subtitle processing
└── uv.lock                   # uv lockfile
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `EMBY_SERVER_URL` | Emby/Jellyfin server URL (required) | - |
| `EMBY_WEB_EMBED_FONT` | Modify Emby JS for web font rendering | `True` |
| `RENAMED_FONT_RESTORE` | Restore renamed font names in subtitles | `True` |
| `SRT_2_ASS_FORMAT` | SRT→ASS conversion format template | `None` |
| `SRT_2_ASS_STYLE` | SRT→ASS conversion style | `None` |
| `SUB_CACHE_SIZE` | Subtitle cache size (entries) | `50` |
| `SUB_CACHE_TTL` | Subtitle cache TTL (minutes) | `60` |
| `FONT_CACHE_SIZE` | Font cache size (entries) | `30` |
| `FONT_CACHE_TTL` | Font cache TTL (minutes) | `30` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ERROR_DISPLAY` | Show error info in subtitle (0-60s) | `0` |
| `MISS_LOGS` | Enable missing font logging | `False` |
| `MISS_GLYPH_LOGS` | Enable missing glyph logging | `False` |
| `DISABLE_ONLINE_FONTS` | Disable online font download | `False` |
| `NGINX_GZIP_COMP_LEVEL` | Nginx gzip level (1-9) | `1` |
| `FONT_DIRS` | Additional font directories (`;`-separated) | - |

## Ports

- **8011**: Python FastAPI service (subtitle processing + batch subset API)
- **8012**: Nginx reverse proxy (client-facing Emby/Jellyfin access)

## Key Dependencies

### Python
- `fastapi` + `uvicorn` — Web framework
- `uharfbuzz` — Font subsetting (HarfBuzz binding)
- `ass` — ASS subtitle parsing
- `sqlalchemy` — Font database ORM (SQLite)
- `aiohttp` — Async HTTP for font downloads
- `cachetools` — TTL/LRU caching
- `watchdog` — Font directory monitoring
- `jsmin` — JS minification for Emby web patching

### Cython/C++
- Performance-critical: UU encoding and ASS analysis
- Requires C++20 compiler
- Build: `python src/py2cy/setup.py`

### Frontend (Vue 3)
- `vue` 3.5 + `vite` 7
- `ant-design-vue` 4 — UI components
- `vue-i18n` — Internationalization (zh-CN, en-US)
- `jszip` + `file-saver` — Download as ZIP

## Data Flow

### Real-time Proxy Mode (Emby/Jellyfin)
1. Client requests subtitle → Nginx intercepts `/videos/*/Subtitles/*`
2. Nginx forwards to Python service (port 8011)
3. Python fetches original subtitle from Emby server
4. `analyseAss` (C++) parses subtitle → extracts `{font_name, weight, italic} → unicode_set`
5. For each font: `FontManager` loads from cache → local DB → online CDN
6. `uharfbuzz` subsets font to only used characters
7. `uuencode` (Cython) encodes subset font binary
8. Embedded `[Fonts]` section inserted before `[Events]` in ASS
9. Modified subtitle returned to client

### Batch Subset Mode (Web UI)
1. User uploads files at `http://[ip]:8011/subset`
2. Frontend sends POST to `/api/subset` with subtitle bytes
3. Same processing pipeline as proxy mode
4. Results returned for download (individual or ZIP)

## CI/CD

GitHub Actions workflows build multi-architecture Docker images (amd64 + arm64):
- `build-builder-multiarch.yml` — Builds builder image (triggered by Cython/frontend changes)
- `build.yml` — Builds runtime images (triggered after builder completes)
- `build-one-step.yml` — Manual trigger for single-stage build

Images published to `riderlty/fontinass` on Docker Hub.

## Code Conventions

- Python 3.10+ (uses `match`, type hints with `|`, `str | None`)
- Async-first: FastAPI + asyncio event loop throughout
- Logging: `coloredlogs` with emoji-prefixed format
- All user-facing text in README and UI is primarily in Chinese
- Font database uses SQLite with SQLAlchemy ORM
- Path handling: `Path.as_posix()` for cross-platform compatibility
- File paths stored in DB as Base64-encoded strings (for unicode path support)
