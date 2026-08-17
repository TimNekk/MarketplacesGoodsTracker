FROM ghcr.io/astral-sh/uv:0.7.13 AS uv

FROM python:3.12-slim-bookworm AS builder

COPY --from=uv /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

RUN --mount=type=cache,target=/root/.cache/camoufox \
    .venv/bin/camoufox fetch && \
    cp -r /root/.cache/camoufox /camoufox-cache

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    libgtk-3-0 \
    libx11-xcb1 \
    libasound2 \
    libdbus-glib-1-2 \
    libxtst6 \
    libxrandr2 \
    libxcomposite1 \
    libxdamage1 \
    libxi6 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libnss3 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m appuser \
    && mkdir -p /tmp/.X11-unix \
    && chown root:root /tmp/.X11-unix \
    && chmod 1777 /tmp/.X11-unix

COPY --from=builder --chown=appuser:appuser /app /app
COPY --from=builder --chown=appuser:appuser /camoufox-cache /home/appuser/.cache/camoufox
COPY --chown=appuser:appuser entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh scripts/ozon_login_vnc.sh

USER appuser

ENTRYPOINT ["/entrypoint.sh"]