# syntax=docker/dockerfile:1.7
# Multi-stage build: install deps with pip into a venv, then ship a slim runtime.
FROM python:3.14-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
# LICENSE must be copied — pyproject.toml declares `license = { file = "LICENSE" }`,
# so the wheel build fails without it.
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN python -m venv /app/.venv \
    && /app/.venv/bin/pip install --no-cache-dir .

# ---------------------------------------------------------------------------

FROM python:3.14-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    MCP_TRANSPORT=sse \
    PORT=8000

# SEC-007: an explicit UID above 10000, not the 100-999 system range that
# `useradd --system` would pick. A high, fixed UID cannot collide with a host
# user if the container is ever run with a bind mount, and it stays stable
# across rebuilds instead of depending on package install order.
RUN groupadd --gid 10001 mcp \
    && useradd --uid 10001 --gid 10001 --home-dir /app --shell /usr/sbin/nologin mcp

WORKDIR /app
COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv

USER 10001:10001
EXPOSE 8000

# MCP_API_KEY must be provided at runtime — the server fails loud if missing.
CMD ["python", "-m", "amtsblatt_mcp.server"]
