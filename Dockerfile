# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS builder
WORKDIR /build
COPY requirements.txt ./
COPY pyproject.toml ./
COPY src ./src
RUN --mount=type=secret,id=proxy_ca \
    PIP_CERT=${PIP_CERT:-/run/secrets/proxy_ca} \
    sh -c 'if [ ! -f "$PIP_CERT" ]; then unset PIP_CERT; fi; python -m pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt && python -m pip wheel --no-deps --wheel-dir /wheels .'

FROM python:3.12-slim-bookworm AS runtime
ARG APP_REVISION=unknown
LABEL org.opencontainers.image.revision=$APP_REVISION
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_REVISION=$APP_REVISION
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels logs-ai \
    && rm -rf /wheels \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --chown=10001:10001 migrations ./migrations
COPY --chmod=755 scripts/start.sh ./start.sh
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
CMD ["./start.sh"]
