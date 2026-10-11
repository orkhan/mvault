# syntax=docker/dockerfile:1.7
#
# Two image flavours from one file (docker build --target <name>):
#   slim - the app only. Bring your own PostgreSQL and S3-compatible storage.
#   aio  - all-in-one: the app + PostgreSQL + MinIO supervised by s6-overlay. Either dependency is
#          skipped automatically when you point the app at your own (DB_HOST/DATABASE_URL, S3_ENDPOINT_URL).
# Both are multi-arch (linux/amd64, linux/arm64). The reverse proxy is deliberately NOT included.

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG GO_IMAGE=golang:1.26-bookworm
# MinIO is built from the pinned upstream tag: the official images were withdrawn, and building from
# source avoids trusting a third-party mirror. Bump MINIO_TAG and MINIO_COMMIT together
# (commit = `git rev-parse <tag>^{commit}` in github.com/minio/minio).
ARG MINIO_TAG=RELEASE.2025-10-15T17-29-55Z
ARG MINIO_COMMIT=9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a
ARG S6_VERSION=3.2.0.3

# ---- MinIO (AGPL-3.0), cross-compiled on the build platform --------------------------------------
FROM --platform=$BUILDPLATFORM ${GO_IMAGE} AS minio-build
ARG TARGETARCH
ARG MINIO_TAG
ARG MINIO_COMMIT
ENV CGO_ENABLED=0 GOTOOLCHAIN=local GOFLAGS=-mod=readonly
WORKDIR /src
RUN git -c advice.detachedHead=false clone --depth 1 --branch "${MINIO_TAG}" --single-branch https://github.com/minio/minio.git . \
    && head="$(git rev-parse HEAD)" \
    && if [ "$head" != "${MINIO_COMMIT}" ]; then echo "FATAL: ${MINIO_TAG} resolves to ${head}, expected ${MINIO_COMMIT}" >&2; exit 1; fi
RUN set -eu; \
    ver="$(printf '%s' "${MINIO_TAG}" | sed -nE 's/^RELEASE\.([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2})-([0-9]{2})-([0-9]{2})Z$/\1T\2:\3:\4Z/p')"; \
    [ -n "$ver" ] || { echo "FATAL: unexpected MINIO_TAG ${MINIO_TAG}" >&2; exit 1; }; \
    ldflags="$(MINIO_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "$ver")"; \
    GOOS=linux GOARCH="${TARGETARCH}" go build -trimpath -ldflags "$ldflags" -o /out/minio . ; \
    mkdir -p /out/licenses && cp LICENSE CREDITS /out/licenses/

# ---- s6-overlay (MIT), checksum-verified --------------------------------------------------------
FROM scratch AS s6-noarch
ARG S6_VERSION
ADD --checksum=sha256:ca79e39c9fea1ccfb6857a0eb13df7e7e12bc1b09454c4158b4075ade5a870ee https://github.com/just-containers/s6-overlay/releases/download/v${S6_VERSION}/s6-overlay-noarch.tar.xz /s6-noarch.tar.xz
FROM scratch AS s6-amd64
ARG S6_VERSION
ADD --checksum=sha256:01eb9a6dce10b5428655974f1903f48e7ba7074506dfb262e85ffab64a5498f2 https://github.com/just-containers/s6-overlay/releases/download/v${S6_VERSION}/s6-overlay-x86_64.tar.xz /s6-arch.tar.xz
FROM scratch AS s6-arm64
ARG S6_VERSION
ADD --checksum=sha256:3a078ef3720a6f16cc93fbd748bdf1b17c9e9ff4ead67947e9565d93379d4168 https://github.com/just-containers/s6-overlay/releases/download/v${S6_VERSION}/s6-overlay-aarch64.tar.xz /s6-arch.tar.xz
FROM s6-${TARGETARCH} AS s6-arch

# ---- Python dependencies ------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS wheels
WORKDIR /w
COPY requirements.txt .
RUN pip wheel --no-cache-dir -r requirements.txt -w /wheels

# ---- App (shared by both flavours) --------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN --mount=type=bind,from=wheels,source=/wheels,target=/wheels \
    --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    pip install --no-cache-dir --no-index --find-links=/wheels -r /tmp/requirements.txt
RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin mvault
WORKDIR /app
COPY --chown=mvault:mvault manage.py ./
COPY --chown=mvault:mvault mvault_app ./mvault_app
COPY --chown=mvault:mvault mvault_project ./mvault_project
COPY LICENSE /licenses/mvault-LICENSE
COPY --chmod=0755 docker/entrypoint.sh /usr/local/bin/mvault-entrypoint
ARG VERSION=dev
ARG REVISION=unknown
LABEL org.opencontainers.image.title="mVault" \
      org.opencontainers.image.description="Self-hosted family vault for passwords, cards, secrets, JSON and files" \
      org.opencontainers.image.source="https://github.com/orkhan/mvault" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health/' % os.environ.get('PORT', '8000'))"

# ---- slim: app only -----------------------------------------------------------------------------
FROM app AS slim
USER mvault
ENTRYPOINT ["/usr/local/bin/mvault-entrypoint"]

# ---- aio: app + PostgreSQL + MinIO under s6-overlay ---------------------------------------------
FROM app AS aio
# Debian's postgresql packages would create a default cluster; we run our own under /data/postgres.
RUN mkdir -p /etc/postgresql-common && printf 'create_main_cluster = false\n' > /etc/postgresql-common/createcluster.conf \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-15 xz-utils ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=bind,from=s6-noarch,source=/,target=/s6n --mount=type=bind,from=s6-arch,source=/,target=/s6a \
    tar -C / -Jxpf /s6n/s6-noarch.tar.xz && tar -C / -Jxpf /s6a/s6-arch.tar.xz
COPY --from=minio-build /out/minio /usr/local/bin/minio
COPY --from=minio-build /out/licenses/ /licenses/minio/
RUN useradd --system --uid 10002 --home-dir /data/minio --shell /usr/sbin/nologin minio \
    && mkdir -p /data /run/postgresql && chown postgres:postgres /run/postgresql
COPY docker/rootfs/ /
RUN chmod +x /etc/s6-overlay/scripts/* /etc/s6-overlay/s6-rc.d/*/run /usr/local/bin/mvault-manage
ENV S6_BEHAVIOUR_IF_STAGE2_FAILS=2 S6_CMD_WAIT_FOR_SERVICES_MAXTIME=0 S6_KEEP_ENV=0 \
    PGBIN=/usr/lib/postgresql/15/bin
VOLUME ["/data"]
ENTRYPOINT ["/init"]
