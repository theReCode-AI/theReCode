FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --group scanners

COPY app ./app

FROM python:3.12-slim-bookworm AS runtime

ARG TARGETARCH
ARG OSV_SCANNER_VERSION=2.5.1
ARG GITLEAKS_VERSION=8.30.1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && case "${TARGETARCH}" in \
        amd64) OSV_ARCH=amd64; GITLEAKS_ARCH=x64 ;; \
        arm64) OSV_ARCH=arm64; GITLEAKS_ARCH=arm64 ;; \
        *) OSV_ARCH=amd64; GITLEAKS_ARCH=x64 ;; \
       esac \
    && curl -fsSL \
        "https://github.com/google/osv-scanner/releases/download/v${OSV_SCANNER_VERSION}/osv-scanner_linux_${OSV_ARCH}" \
        -o /usr/local/bin/osv-scanner \
    && curl -fsSL \
        "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${GITLEAKS_ARCH}.tar.gz" \
        | tar -xz -C /usr/local/bin gitleaks \
    && chmod +x /usr/local/bin/osv-scanner /usr/local/bin/gitleaks \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system therecode \
    && useradd --system --gid therecode therecode \
    && mkdir -p /workspace/runs \
    && chown -R therecode:therecode /workspace

COPY --from=builder /app /app
COPY .env ./.env
RUN chown therecode:therecode ./.env

ENV PATH="/app/.venv/bin:/usr/local/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV THERECODE_WORKSPACE_ROOT=/workspace

USER therecode

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
