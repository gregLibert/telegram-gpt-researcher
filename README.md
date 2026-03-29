# Telegram × GPT Researcher

Production-oriented Docker stack that runs **[GPT Researcher](https://github.com/assafelovic/gpt-researcher)** behind a **Telegram bot** with an allowlist, async HTTP calls to the research API, and **PDF reports** produced by **WeasyPrint**.

---

## Architecture overview

| Service | Role |
|--------|------|
| **gpt-researcher** | Upstream-style backend: FastAPI (`uvicorn`), clones a pinned GPT Researcher release in the image, optional retrievers/scrapers (`nodriver`, `zendriver`, BeautifulSoup). |
| **telegram-bot** | Python 3.12 service: validates users, `/research` command, queued background jobs, PDF delivery. |

### Headless browser on Docker (ARM64 / AMD64)

Modern sites and bot checks often expect a real browser. This project installs **nodriver** and **zendriver** (Chrome DevTools–style automation, not Selenium) for browser-backed scraping inside GPT Researcher.

Running Chromium in containers raises three common issues:

1. **Sandbox** — The kernel user namespace sandbox is unsuitable for many Docker setups. The image **renames the real Chromium binary to `chromium-real`** and installs a small **`/usr/bin/chromium` wrapper** that always prepends flags such as **`--no-sandbox`**, **`--disable-dev-shm-usage`**, **`--headless=new`**, **`--disable-gpu`**, and **`--disable-software-rasterizer`**, then forwards every other argument. **`google-chrome`** is symlinked to the same wrapper so launchers that look for “Chrome” still hit the safe entrypoint.

2. **Missing display** — Some toolchains still expect an X server. The GPT Researcher container starts the API under **`xvfb-run -a`** (with **`xvfb`** and **`xauth`** installed) so a virtual framebuffer is available when needed.

3. **Resource limits** — A **`shm_size`** of **2 GB** is recommended for Chromium; the bot caps concurrent research jobs with a semaphore to reduce RAM spikes on small boards (e.g. Orange Pi).

Together, the wrapper + Xvfb + shared memory keep browser-based scraping usable on **both `linux/amd64` and `linux/arm64`**.

### PDF generation (Telegram bot)

Reports are rendered as **PDF** with **[WeasyPrint](https://weasyprint.org/)** (HTML/CSS from Markdown). Tables and long URLs are styled for readable line breaks. The bot sends **only the PDF** to the user (no separate Markdown attachment).

---

## Quick start (pre-built images from GHCR)

After [GitHub Actions](.github/workflows/ci.yml) publishes images, reference them by **`ghcr.io/<owner>/<repository>/`** (all lowercase).

1. **Clone** this repository (or copy the compose snippet and `.env.example`).

2. **Configure secrets** — copy `.env.example` to `.env` and set at least:
   - `OPENAI_API_KEY`, `TAVILY_API_KEY` (and any other keys required by your GPT Researcher config)
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_ALLOWED_USER_IDS` (comma-separated Telegram user IDs)

3. **Define image coordinates** in `.env`, for example:

   ```env
   GHCR_IMAGE_PREFIX=your-github-username/your-repo-name
   APP_VERSION=latest
   ```

4. **Run**:

   ```bash
   docker compose up -d
   ```

Ultra-simplified **`docker-compose.yml`** for end users pulling from GHCR (replace values or use `.env` as above):

```yaml
services:
  gpt-researcher:
    image: ghcr.io/${GHCR_IMAGE_PREFIX}/gpt-researcher:${APP_VERSION:-latest}
    restart: unless-stopped
    shm_size: "2gb"
    ports:
      - "${GPTR_HOST_PORT:-8000}:8000"
    env_file: .env
    environment:
      HOST: 0.0.0.0
      PORT: "8000"
      WORKERS: ${GPTR_WORKERS:-1}
      LOGGING_LEVEL: ${LOGGING_LEVEL:-INFO}
      CHROME_BIN: /usr/bin/chromium
      CHROMIUM_FLAGS: "--headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu --disable-software-rasterizer --disable-setuid-sandbox --window-size=1920,1080 --remote-debugging-port=9222"
      PUPPETEER_SKIP_CHROMIUM_DOWNLOAD: "true"
      PUPPETEER_EXECUTABLE_PATH: /usr/bin/chromium
    volumes:
      - gptr_outputs:/usr/src/app/outputs
      - gptr_my_docs:/usr/src/app/my-docs
      - gptr_logs:/usr/src/app/logs
      - gptr_report_store:/usr/src/app/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/openapi.json', timeout=5).read(1)"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  telegram-bot:
    image: ghcr.io/${GHCR_IMAGE_PREFIX}/telegram-bot:${APP_VERSION:-latest}
    restart: unless-stopped
    depends_on:
      gpt-researcher:
        condition: service_healthy
    env_file: .env
    environment:
      GPTR_API_URL: ${GPTR_API_URL:-http://gpt-researcher:8000}
      BOT_ARTIFACT_DIR: /tmp/bot-artifacts
    volumes:
      - bot_tmp:/tmp/bot-artifacts

volumes:
  gptr_outputs:
  gptr_my_docs:
  gptr_logs:
  gptr_report_store:
  bot_tmp:
```

- **`APP_VERSION`**: use `latest` for the default branch, or a published tag such as **`v1.2.3`** (without the **`v`** prefix in the Docker tag is also common depending on your metadata rules; align with the tags pushed by CI).
- **`GHCR_IMAGE_PREFIX`**: `github.repository` in lowercase, e.g. `octocat/telegram-gpt-researcher`.

For **local builds** instead of GHCR, use the root `docker-compose.yml` in this repo (`build:` contexts for `./services/gpt-researcher` and `./telegram-bot`).

---

## Telegram commands

| Command | Description |
|--------|-------------|
| **`/start`** | Short welcome and pointer to **`/help`**. |
| **`/help`** | Explains **`/research`** and all options below. |
| **`/research [options…] <question>`** | Starts a research job (allowlist enforced). Immediate ack; PDF is sent when ready. |

**`/research` options** (can be chained; the **last** report-type flag wins):

| Flag | GPT Researcher mode |
|------|---------------------|
| **`--deep`** or **`-d`** | Deep research (`deep`). |
| **`--detailed`** | Detailed report (`detailed_report`). |
| **`--outline`** | Outline / plan style (`outline_report`). |
| **`--resource`** | Resource-oriented report (`resource_report`). |

Plain phrases such as “deep learning” are **not** treated as **`--deep`**; use the flag explicitly.

---

## Continuous integration

The [CI workflow](.github/workflows/ci.yml) runs on **pushes to `main`**, **version tags** matching **`v*.*.*`**, and **manual** runs. It:

1. Runs **pytest** for `telegram-bot/tests/` on Ubuntu with Python 3.12 (including OS packages needed by WeasyPrint).
2. After tests pass, builds and pushes **multi-arch** (`linux/amd64`, `linux/arm64`) images **`gpt-researcher`** and **`telegram-bot`** to **GHCR** (`ghcr.io/<owner>/<repo>/<image>`), tagging **`latest`** on the default branch and **semver** tags when a Git tag is pushed.

Forks need **Actions** enabled and **Packages** write access for `GITHUB_TOKEN` (default for pushes on `main` in the same repo).

---

## Upstream license

GPT Researcher is developed by [**assafelovic/gpt-researcher**](https://github.com/assafelovic/gpt-researcher) under its own license. This repository orchestrates Docker images and a Telegram layer around it; refer to the upstream project for engine licensing and citations.
