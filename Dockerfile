ARG UV_VERSION=0.12.9
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PRESENCE_DATABASE_PATH=/data/presence.db

WORKDIR /app

COPY --from=uv /uv /uvx /bin/

RUN useradd --create-home --uid 10001 kirtap \
    && mkdir /data \
    && chown kirtap:kirtap /data

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY --chown=kirtap:kirtap src ./src
RUN uv sync --locked --no-dev

USER kirtap

VOLUME ["/data"]

CMD ["/app/.venv/bin/kirtap"]
