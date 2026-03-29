# GPT Researcher — image alignée sur l’officielle (Python 3.12 + Bookworm),
# sans dépôt Google Chrome : Chromium + chromium-driver uniquement (adapté ARM64 / Orange Pi 5).
# Référence : https://github.com/assafelovic/gpt-researcher

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm AS install-browser

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        chromium \
        chromium-driver \
        fontconfig \
        fonts-liberation \
        fonts-noto-color-emoji \
        wget \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/chromium /usr/bin/google-chrome \
    && chromium --version \
    && (chromedriver --version || true)

FROM install-browser AS gpt-researcher-install

ENV PIP_ROOT_USER_ACTION=ignore
WORKDIR /usr/src/app

ARG GPT_RESEARCHER_REF=main
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --depth 1 --branch "${GPT_RESEARCHER_REF}" \
        https://github.com/assafelovic/gpt-researcher.git /usr/src/app \
    && rm -rf /usr/src/app/.git

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt --upgrade --prefer-binary \
    && pip install --no-cache-dir -r multi_agents/requirements.txt --upgrade --prefer-binary

FROM gpt-researcher-install AS gpt-researcher

ARG HOST=0.0.0.0
ENV HOST=${HOST}
ARG PORT=8000
ENV PORT=${PORT}
EXPOSE ${PORT}

ARG WORKERS=1
ENV WORKERS=${WORKERS}

# Binaire Chromium + flags headless (documentés ; le code Selenium ajoute déjà --no-sandbox sur Linux)
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMIUM_FLAGS="--headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu --disable-software-rasterizer --disable-setuid-sandbox --window-size=1920,1080 --remote-debugging-port=9222"
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

RUN useradd -ms /bin/bash gpt-researcher \
    && mkdir -p /usr/src/app/outputs /usr/src/app/my-docs /usr/src/app/logs /usr/src/app/data \
    && chown -R gpt-researcher:gpt-researcher /usr/src/app \
    && chmod 777 /usr/src/app/outputs

USER gpt-researcher
WORKDIR /usr/src/app

CMD uvicorn main:app --host ${HOST} --port ${PORT} --workers ${WORKERS}
