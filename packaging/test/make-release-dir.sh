#!/bin/sh
# Assemble a release directory that follows the release-asset contract, for testing install.sh offline:
#
#   packaging/test/make-release-dir.sh <version> <out-dir> [minio-binary ...]
#
# Each extra argument is a MinIO binary named minio-<os>-<arch> (e.g. ./out/minio-linux-amd64).
# Then:  MVAULT_RELEASE_BASE=<out-dir> sh install.sh --version <version> ...
set -eu
version="${1:?usage: make-release-dir.sh <version> <out-dir> [minio-binary ...]}"
out="${2:?usage: make-release-dir.sh <version> <out-dir> [minio-binary ...]}"
shift 2
root="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$out"
TAR_FLAGS=""
if tar --help 2>&1 | grep -q -- --no-xattrs; then TAR_FLAGS="--no-xattrs"; fi # keep macOS extended attributes out of the archive
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
top="$stage/mvault-$version"
mkdir -p "$top"
cd "$root"
for item in manage.py mvault_app mvault_project requirements.txt packaging LICENSE; do
    cp -R "$item" "$top/"
done
find "$top" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf "$top/packaging/test"
COPYFILE_DISABLE=1 tar $TAR_FLAGS -C "$stage" -czf "$out/mvault-$version-app.tar.gz" "mvault-$version"
cp "$root/install.sh" "$out/install.sh"
for bin in "$@"; do cp "$bin" "$out/$(basename "$bin")"; done
printf '%s\n' "$version" >"$out/VERSION"
(
    cd "$out"
    rm -f SHA256SUMS
    for f in mvault-"$version"-app.tar.gz minio-* install.sh; do
        [ -f "$f" ] || continue
        if command -v sha256sum >/dev/null 2>&1; then sha256sum "$f"; else shasum -a 256 "$f"; fi
    done >SHA256SUMS
)
echo "release directory ready: $out"
