FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-dev --group scanners

COPY app ./app
# app/.env is included via COPY app (required for Cloud Run settings)

FROM python:3.12-slim-bookworm AS runtime

ARG TARGETARCH
ARG OSV_SCANNER_VERSION=2.5.1
ARG GITLEAKS_VERSION=8.30.1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
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
    && chmod +x \
        /usr/local/bin/osv-scanner \
        /usr/local/bin/gitleaks \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system therecode \
    && useradd --system --gid therecode therecode \
    && mkdir -p /workspace/runs \
    && chown -R therecode:therecode /workspace

COPY --from=builder /app /app
RUN chown -R therecode:therecode /app /workspace

ENV PATH="/app/.venv/bin:/usr/local/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV THERECODE_WORKSPACE_ROOT=/workspace
ENV THERECODE_HOST=0.0.0.0
ENV THERECODE_PORT=8000

USER therecode

EXPOSE 8000

# Cloud Run injects PORT; bind 0.0.0.0 so the platform health check succeeds.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]