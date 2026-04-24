FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY insta_dl ./insta_dl

RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 1000 insta \
    && mkdir -p /data && chown -R insta:insta /data

USER insta
WORKDIR /data

ENTRYPOINT ["insta-dl"]
CMD ["--help"]
