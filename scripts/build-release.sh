#!/usr/bin/env bash
# Build the release assets that install.sh / the Proxmox installer download.
#
#   scripts/build-release.sh [--version X.Y.Z] [--out DIR] app|minio|checksums|all
#
#   app        dist/mvault-X.Y.Z-app.tar.gz   (arch independent; top-level dir mvault-X.Y.Z/)
#   minio      dist/minio-{linux,darwin}-{amd64,arm64}   built from the pinned upstream tag + commit
#              (MINIO_TAG / MINIO_COMMIT are read from the Dockerfile: the single source of truth)
#   checksums  dist/SHA256SUMS over everything in dist/
#   all        app + minio + install.sh copy + checksums
#
# Needs: bash, tar, git (+ go for `minio`). Run from anywhere inside the repository.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/dist"
VERSION=""
TARGETS="${TARGETS:-linux/amd64 linux/arm64 darwin/amd64 darwin/arm64}"

die() { echo "build-release: $*" >&2; exit 1; }
sha256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }

while [ $# -gt 0 ]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        app|minio|checksums|all) CMD="$1"; shift ;;
        -h|--help) sed -n '2,13p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) die "unknown argument: $1" ;;
    esac
done
CMD="${CMD:-all}"

app_version() { sed -nE 's/^APP_VERSION = "([^"]+)".*/\1/p' "$ROOT/mvault_project/settings.py"; }
[ -n "$VERSION" ] || VERSION="$(app_version)"
[ -n "$VERSION" ] || die "could not determine the version"
[ "$VERSION" = "$(app_version)" ] || die "version $VERSION does not match APP_VERSION $(app_version) in mvault_project/settings.py"
mkdir -p "$OUT"

build_app() {
    local name="mvault-$VERSION" stage tarball="$OUT/mvault-$VERSION-app.tar.gz"
    stage="$(mktemp -d)"
    mkdir -p "$stage/$name"
    cp "$ROOT/manage.py" "$ROOT/requirements.txt" "$ROOT/LICENSE" "$stage/$name/"
    cp -R "$ROOT/mvault_app" "$ROOT/mvault_project" "$stage/$name/"
    [ -d "$ROOT/packaging" ] && cp -R "$ROOT/packaging" "$stage/$name/"
    find "$stage" \( -name '__pycache__' -o -name '*.pyc' -o -name '.DS_Store' \) -prune -exec rm -rf {} +
    local opts=()
    if tar --version 2>/dev/null | grep -q 'GNU tar'; then
        opts=(--sort=name --owner=0 --group=0 --numeric-owner --mtime="@${SOURCE_DATE_EPOCH:-$(git -C "$ROOT" log -1 --format=%ct 2>/dev/null || date +%s)}")
    fi
    COPYFILE_DISABLE=1 tar "${opts[@]}" -C "$stage" -czf "$tarball" "$name"
    rm -rf "$stage"
    echo "built $tarball"
}

build_minio() {
    command -v go >/dev/null 2>&1 || die "go is required to build MinIO"
    local tag commit work ver ldflags
    tag="$(sed -nE 's/^ARG MINIO_TAG=(.*)$/\1/p' "$ROOT/Dockerfile")"
    commit="$(sed -nE 's/^ARG MINIO_COMMIT=(.*)$/\1/p' "$ROOT/Dockerfile")"
    [ -n "$tag" ] && [ -n "$commit" ] || die "MINIO_TAG / MINIO_COMMIT not found in Dockerfile"
    work="$(mktemp -d)"
    trap 'rm -rf "$work"' RETURN
    git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$tag" --single-branch https://github.com/minio/minio.git "$work/src"
    [ "$(git -C "$work/src" rev-parse HEAD)" = "$commit" ] || die "tag $tag does not resolve to the pinned commit $commit"
    ver="$(printf '%s' "$tag" | sed -nE 's/^RELEASE\.([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2})-([0-9]{2})-([0-9]{2})Z$/\1T\2:\3:\4Z/p')"
    [ -n "$ver" ] || die "unexpected MINIO_TAG: $tag"
    (
        cd "$work/src"
        ldflags="$(CGO_ENABLED=0 MINIO_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "$ver")"
        for target in $TARGETS; do
            echo "building minio for $target ($tag)"
            CGO_ENABLED=0 GOOS="${target%/*}" GOARCH="${target#*/}" go build -trimpath -ldflags "$ldflags" -o "$OUT/minio-${target%/*}-${target#*/}" .
        done
        mkdir -p "$OUT/licenses" && cp LICENSE "$OUT/licenses/minio-LICENSE" && cp CREDITS "$OUT/licenses/minio-CREDITS"
    )
}

copy_installer() {
    if [ -f "$ROOT/install.sh" ]; then cp "$ROOT/install.sh" "$OUT/install.sh"; else echo "note: install.sh not found, skipping"; fi
}

checksums() {
    (
        cd "$OUT"
        : > SHA256SUMS
        for f in *; do
            { [ -f "$f" ] && [ "$f" != SHA256SUMS ]; } || continue
            sha256 "$f" >> SHA256SUMS
        done
    )
    echo "wrote $OUT/SHA256SUMS"; cat "$OUT/SHA256SUMS"
}

case "$CMD" in
    app) build_app ;;
    minio) build_minio ;;
    checksums) checksums ;;
    all) build_app; build_minio; copy_installer; checksums ;;
esac
