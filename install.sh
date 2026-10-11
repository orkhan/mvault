#!/bin/sh
# mVault native installer for Linux (systemd) and macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/install.sh | sudo sh        # Linux
#   curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/install.sh | sh             # macOS
#   curl -fsSL .../install.sh | sudo sh -s -- --version 0.4.0 --base-url https://vault.example.com
#
# Installs mVault together with PostgreSQL and MinIO (each can be skipped to use your own), or upgrades an
# existing installation. Safe to re-run: existing secrets are never overwritten. See `--help`.
set -eu

REPO="${MVAULT_GITHUB_REPO:-orkhan/mvault}"
UV_VERSION="0.13.0"
PYTHON_VERSION="3.12"
PG_BREW_FORMULA="postgresql@17"

# --- helpers -------------------------------------------------------------------------------------------
if [ -t 1 ]; then B=$(printf '\033[1m'); R=$(printf '\033[0m'); else B=""; R=""; fi
log() { printf '%s==>%s %s\n' "$B" "$R" "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

usage() {
    cat <<'EOF'
mVault installer

Usage: install.sh [options]

  --version X.Y.Z        install this release (default: latest)
  --prefix DIR           Linux: application directory (default /opt/mvault)
                         macOS: base directory for everything (default ~/Library/Application Support/mvault)
  --bin-dir DIR          where to put the mvault command (default /usr/local/bin; macOS: ~/.local/bin if /usr/local/bin is not writable)
  --port N               web port (default 8000)
  --bind ADDR            bind address (default 0.0.0.0 on Linux, 127.0.0.1 on macOS)
  --base-url URL         public URL, e.g. https://vault.example.com (recommended behind a reverse proxy)
  --admin-email EMAIL    first administrator (default admin@mvault.local)

  --no-postgres          do not install PostgreSQL; use --database-url
  --database-url URL     postgres://user:password@host:5432/dbname
  --pg-port N            macOS: port of the private PostgreSQL cluster (default 54329)
  --no-minio             do not install MinIO; use --s3-endpoint/--s3-access-key/--s3-secret-key
  --s3-endpoint URL  --s3-access-key KEY  --s3-secret-key SECRET  --provision-buckets
  --no-storage           run without object storage (icons, avatars and file records disabled)

  --upgrade              upgrade an existing installation (re-running does this automatically)
  --no-start             install but do not start services
  --no-systemd           Linux: install everything but do not install/enable systemd units
  --uninstall [--purge]  remove mVault (data is kept unless --purge)
  --yes                  never ask questions
  -h, --help

Environment: MVAULT_RELEASE_BASE (directory or URL holding the release assets, for mirrors and testing).
EOF
}

os_ids() { # "debian ubuntu"-style identifiers; read in a subshell because os-release defines VERSION, NAME, ID...
    # shellcheck disable=SC1091
    ( . /etc/os-release 2>/dev/null && printf '%s %s' "${ID:-}" "${ID_LIKE:-}" )
}

rand_hex() { head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'; }

ask() { # ask <prompt> -> reads from the terminal even when the script itself is piped
    [ "$ASSUME_YES" = 1 ] && return 1
    [ -r /dev/tty ] || return 1
    printf '%s ' "$1" >/dev/tty
    read -r ANSWER </dev/tty || return 1
    [ -n "$ANSWER" ]
}

fetch() { # fetch <url-or-path> <dest>
    case "$1" in
        http://* | https://*)
            if have curl; then curl -fsSL --retry 3 -o "$2" "$1"; else wget -q -O "$2" "$1"; fi
            ;;
        file://*) cp "${1#file://}" "$2" ;;
        *) cp "$1" "$2" ;;
    esac
}

sha256_of() {
    if have sha256sum; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

kv_get() { # kv_get <file> <KEY>: value of KEY='value' / KEY=value
    [ -f "$1" ] || return 0
    sed -n "s/^$2=//p" "$1" | tail -n 1 | sed "s/^'\\(.*\\)'\$/\\1/"
}

kv_put() { # kv_put <file> <KEY> <value>: add KEY only when it is not set yet (never overwrite)
    case "$3" in *"'"* | *'
'*) die "value for $2 must not contain quotes or newlines" ;; esac
    if [ -f "$1" ] && grep -q "^$2=" "$1"; then return 0; fi
    printf "%s='%s'\n" "$2" "$3" >>"$1"
}

# --- arguments -----------------------------------------------------------------------------------------
VERSION="${MVAULT_VERSION:-}"
PREFIX_ARG=""
BIN_DIR_ARG=""
PORT="8000"
BIND=""
BASE_URL=""
ADMIN_EMAIL=""
WITH_POSTGRES=1
DATABASE_URL_ARG=""
PG_PORT="54329"
WITH_MINIO=1
WITH_STORAGE=1
S3_ENDPOINT_ARG=""
S3_KEY_ARG=""
S3_SECRET_ARG=""
PROVISION_BUCKETS_ARG=""
UPGRADE=0
START=1
SYSTEMD=1
UNINSTALL=0
PURGE=0
ASSUME_YES=0
[ -n "${MVAULT_SKIP_SERVICES:-}" ] && { START=0; SYSTEMD=0; }

while [ $# -gt 0 ]; do
    case "$1" in
        --version) VERSION="${2:?--version needs a value}"; shift ;;
        --prefix) PREFIX_ARG="${2:?--prefix needs a value}"; shift ;;
        --bin-dir) BIN_DIR_ARG="${2:?--bin-dir needs a value}"; shift ;;
        --port) PORT="${2:?--port needs a value}"; shift ;;
        --bind) BIND="${2:?--bind needs a value}"; shift ;;
        --base-url) BASE_URL="${2:?--base-url needs a value}"; shift ;;
        --admin-email) ADMIN_EMAIL="${2:?--admin-email needs a value}"; shift ;;
        --no-postgres) WITH_POSTGRES=0 ;;
        --database-url) DATABASE_URL_ARG="${2:?--database-url needs a value}"; WITH_POSTGRES=0; shift ;;
        --pg-port) PG_PORT="${2:?--pg-port needs a value}"; shift ;;
        --no-minio) WITH_MINIO=0 ;;
        --s3-endpoint) S3_ENDPOINT_ARG="${2:?--s3-endpoint needs a value}"; WITH_MINIO=0; shift ;;
        --s3-access-key) S3_KEY_ARG="${2:?--s3-access-key needs a value}"; shift ;;
        --s3-secret-key) S3_SECRET_ARG="${2:?--s3-secret-key needs a value}"; shift ;;
        --provision-buckets) PROVISION_BUCKETS_ARG=true ;;
        --no-storage) WITH_STORAGE=0; WITH_MINIO=0 ;;
        --upgrade) UPGRADE=1 ;;
        --no-start) START=0 ;;
        --no-systemd) SYSTEMD=0; START=0 ;;
        --uninstall) UNINSTALL=1 ;;
        --purge) PURGE=1 ;;
        --yes | -y) ASSUME_YES=1 ;;
        -h | --help) usage; exit 0 ;;
        *) usage >&2; die "unknown option: $1" ;;
    esac
    shift
done
[ -t 0 ] || [ -r /dev/tty ] || ASSUME_YES=1

case "${MVAULT_RELEASE_BASE:-}" in
    "" | http://* | https://* | file://* | /*) ;;
    *) MVAULT_RELEASE_BASE="$(pwd)/$MVAULT_RELEASE_BASE" ;;
esac
cd /

# --- platform --------------------------------------------------------------------------------------------
OS="$(uname -s)"
case "$(uname -m)" in
    x86_64 | amd64) ARCH=amd64 ;;
    aarch64 | arm64) ARCH=arm64 ;;
    *) die "unsupported CPU architecture: $(uname -m) (supported: x86_64, arm64)" ;;
esac
case "$OS" in
    Linux) MODE=system; OSNAME=linux ;;
    Darwin) MODE=user; OSNAME=darwin ;;
    *) die "unsupported operating system: $OS (supported: Linux, macOS)" ;;
esac
umask 022

if [ "$MODE" = system ]; then
    [ "$(id -u)" -eq 0 ] || die "run as root: curl -fsSL https://raw.githubusercontent.com/$REPO/main/install.sh | sudo sh"
    have systemctl || [ "$SYSTEMD" = 0 ] || die "systemd is required on Linux (use --no-systemd to install without services)"
    PREFIX="${PREFIX_ARG:-/opt/mvault}"
    CONF_DIR="/etc/mvault"
    DATA_DIR="/var/lib/mvault"
    BIN_DIR="/usr/local/bin"
    MINIO_BIN="/usr/local/bin/mvault-minio"
    LAYOUT_FILE="$CONF_DIR/layout.env"
    BIND="${BIND:-0.0.0.0}"
else
    [ "$(id -u)" -ne 0 ] || die "on macOS run this as your normal user, not root (Homebrew refuses to run as root)"
    BASE="${PREFIX_ARG:-$HOME/Library/Application Support/mvault}"
    PREFIX="$BASE/app"
    CONF_DIR="$BASE"
    DATA_DIR="$BASE/data"
    MINIO_BIN="$BASE/bin/minio"
    LAYOUT_FILE="$BASE/layout.env"
    BIND="${BIND:-127.0.0.1}"
    if [ -w /usr/local/bin ]; then BIN_DIR=/usr/local/bin; else BIN_DIR="$HOME/.local/bin"; fi
fi

# An existing installation (layout.env) turns a plain re-run into an upgrade that reuses its settings.
for candidate in "${MVAULT_LAYOUT:-}" /etc/mvault/layout.env "$HOME/.config/mvault/layout.env" "$HOME/Library/Application Support/mvault/layout.env"; do
    if [ -n "$candidate" ] && [ -f "$candidate" ]; then EXISTING_LAYOUT="$candidate"; break; fi
done
EXISTING_LAYOUT="${EXISTING_LAYOUT:-}"
EX_PG_BIN=""
YES_FLAG=""
[ "$ASSUME_YES" = 1 ] && YES_FLAG="--yes"

if [ "$UNINSTALL" = 1 ]; then
    have mvault || [ -x "$BIN_DIR/mvault" ] || die "mVault does not appear to be installed (no mvault command found)"
    cmd="$(command -v mvault || printf '%s' "$BIN_DIR/mvault")"
    if [ "$PURGE" = 1 ]; then exec "$cmd" uninstall --purge $YES_FLAG; fi
    exec "$cmd" uninstall $YES_FLAG
fi

if [ -n "$EXISTING_LAYOUT" ]; then
    UPGRADE=1 # an existing installation is always upgraded in place
    # Reuse where the existing installation lives and which parts it runs.
    EX_PG_MODE="$(kv_get "$EXISTING_LAYOUT" MVAULT_PG_MODE)"
    EX_MINIO_MODE="$(kv_get "$EXISTING_LAYOUT" MVAULT_MINIO_MODE)"
    EX_PG_BIN="$(kv_get "$EXISTING_LAYOUT" MVAULT_PG_BIN)"
    EX_PG_PORT="$(kv_get "$EXISTING_LAYOUT" MVAULT_PG_PORT)"
    PREFIX="$(kv_get "$EXISTING_LAYOUT" MVAULT_PREFIX)"
    CONF_DIR="$(kv_get "$EXISTING_LAYOUT" MVAULT_CONF_DIR)"
    DATA_DIR="$(kv_get "$EXISTING_LAYOUT" MVAULT_DATA_DIR)"
    MINIO_BIN="$(kv_get "$EXISTING_LAYOUT" MVAULT_MINIO_BIN)"
    EX_BIN_DIR="$(kv_get "$EXISTING_LAYOUT" MVAULT_BIN_DIR)"
    [ -z "$EX_BIN_DIR" ] || BIN_DIR="$EX_BIN_DIR"
    [ "$EX_PG_MODE" = external ] && WITH_POSTGRES=0
    [ "$EX_MINIO_MODE" = embedded ] || WITH_MINIO=0
    [ "$EX_MINIO_MODE" = none ] && WITH_STORAGE=0
    [ -n "$EX_PG_PORT" ] && PG_PORT="$EX_PG_PORT"
    log "Existing installation found ($EXISTING_LAYOUT): upgrading and keeping all settings and secrets"
fi
[ -z "$BIN_DIR_ARG" ] || BIN_DIR="$BIN_DIR_ARG"
ENV_FILE="$CONF_DIR/mvault.env"
MINIO_ENV_FILE="$CONF_DIR/minio.env"
LAYOUT_FILE="$CONF_DIR/layout.env" # canonical copy; on macOS a pointer copy in ~/.config makes custom prefixes discoverable

# Validate what a fresh install needs before anything is downloaded or changed.
if [ ! -f "$ENV_FILE" ]; then
    if [ "$WITH_POSTGRES" = 0 ] && [ -z "$DATABASE_URL_ARG" ]; then
        if ask "PostgreSQL URL (postgres://user:password@host:5432/dbname):"; then DATABASE_URL_ARG="$ANSWER"; fi
        [ -n "$DATABASE_URL_ARG" ] || die "with --no-postgres you must pass --database-url postgres://user:password@host:5432/dbname"
    fi
    if [ "$WITH_STORAGE" = 1 ] && [ "$WITH_MINIO" = 0 ]; then
        if [ -z "$S3_ENDPOINT_ARG" ] && ask "S3 endpoint URL (e.g. http://minio.lan:9000):"; then S3_ENDPOINT_ARG="$ANSWER"; fi
        if [ -n "$S3_ENDPOINT_ARG" ] && [ -z "$S3_KEY_ARG" ] && ask "S3 access key:"; then S3_KEY_ARG="$ANSWER"; fi
        if [ -n "$S3_ENDPOINT_ARG" ] && [ -z "$S3_SECRET_ARG" ] && ask "S3 secret key:"; then S3_SECRET_ARG="$ANSWER"; fi
        [ -n "$S3_ENDPOINT_ARG" ] && [ -n "$S3_KEY_ARG" ] && [ -n "$S3_SECRET_ARG" ] \
            || die "with --no-minio pass --s3-endpoint, --s3-access-key and --s3-secret-key, or use --no-storage"
    fi
fi

# --- release lookup ----------------------------------------------------------------------------------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM

if [ -z "$VERSION" ]; then
    if [ -n "${MVAULT_RELEASE_BASE:-}" ]; then
        fetch "$MVAULT_RELEASE_BASE/VERSION" "$TMP/VERSION" 2>/dev/null || die "set --version when MVAULT_RELEASE_BASE is used"
        VERSION="$(tr -d ' \n' <"$TMP/VERSION")"
    else
        have curl || have wget || die "curl or wget is required"
        log "Looking up the latest release"
        fetch "https://api.github.com/repos/$REPO/releases/latest" "$TMP/latest.json" || die "could not query GitHub for the latest release (no release published yet, or no network access); try --version X.Y.Z"
        VERSION="$(sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' "$TMP/latest.json" | head -n 1)"
        [ -n "$VERSION" ] || die "could not determine the latest release version"
    fi
fi
VERSION="${VERSION#v}"
RELEASE_BASE="${MVAULT_RELEASE_BASE:-https://github.com/$REPO/releases/download/v$VERSION}"
if [ "$UPGRADE" = 1 ]; then log "Upgrading mVault to $VERSION ($OSNAME/$ARCH, $MODE install)"; else log "Installing mVault $VERSION ($OSNAME/$ARCH, $MODE install)"; fi

for tool in tar gzip; do have "$tool" || die "$tool is required"; done
have curl || have wget || die "curl or wget is required"
have sha256sum || have shasum || die "sha256sum or shasum is required"

# --- download and verify ------------------------------------------------------------------------------------
fetch "$RELEASE_BASE/SHA256SUMS" "$TMP/SHA256SUMS" || die "could not download SHA256SUMS from $RELEASE_BASE"

download_verified() { # download_verified <asset-name> <dest>
    fetch "$RELEASE_BASE/$1" "$2" || die "could not download $1"
    want="$(awk -v n="$1" '$2 == n || $2 == "*" n {print $1}' "$TMP/SHA256SUMS")"
    [ -n "$want" ] || die "$1 is not listed in SHA256SUMS"
    got="$(sha256_of "$2")"
    [ "$want" = "$got" ] || die "checksum mismatch for $1 (expected $want, got $got)"
}

log "Downloading the application"
download_verified "mvault-$VERSION-app.tar.gz" "$TMP/app.tar.gz"
if [ "$WITH_MINIO" = 1 ]; then
    log "Downloading MinIO"
    download_verified "minio-$OSNAME-$ARCH" "$TMP/minio"
fi

# --- users, directories ---------------------------------------------------------------------------------------
if [ "$MODE" = system ] && ! id mvault >/dev/null 2>&1; then
    log "Creating system user 'mvault'"
    nologin="$(command -v nologin || printf /usr/sbin/nologin)"
    useradd --system --home-dir "$DATA_DIR" --shell "$nologin" --user-group mvault 2>/dev/null \
        || adduser --system --home "$DATA_DIR" --shell "$nologin" --group mvault
fi
mkdir -p "$PREFIX/releases" "$CONF_DIR" "$DATA_DIR/backups" "$DATA_DIR/logs" "$DATA_DIR/run"
if [ "$MODE" = system ]; then
    chown mvault:mvault "$DATA_DIR" "$DATA_DIR/backups" "$DATA_DIR/logs" "$DATA_DIR/run"
    chmod 750 "$DATA_DIR"
    chown root:mvault "$CONF_DIR"
    chmod 750 "$CONF_DIR"
else
    chmod 700 "$CONF_DIR"
fi

# --- unpack the release --------------------------------------------------------------------------------------
REL_DIR="$PREFIX/releases/$VERSION"
log "Unpacking into $REL_DIR"
rm -rf "$TMP/unpack" "$REL_DIR.new"
mkdir -p "$TMP/unpack"
tar -xzf "$TMP/app.tar.gz" -C "$TMP/unpack"
SRC="$(find "$TMP/unpack" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
[ -f "$SRC/manage.py" ] || die "the release archive does not contain manage.py"
mv "$SRC" "$REL_DIR.new"
printf '%s\n' "$VERSION" >"$REL_DIR.new/VERSION"
rm -rf "$REL_DIR"
mv "$REL_DIR.new" "$REL_DIR"

# --- Python via uv (system Python is irrelevant) ---------------------------------------------------------------
uv_triple() {
    case "$OSNAME-$ARCH" in
        linux-amd64) printf 'x86_64-unknown-linux-gnu 1468ebd5a5541121837c5a2817b9972ba6090fa6caa3d142620850a47fb75154' ;;
        linux-arm64) printf 'aarch64-unknown-linux-gnu 3ccfb6af6e242433eb552f7d9676abd5412c6595c497e990d9c8cb7b5bd4d2c3' ;;
        darwin-amd64) printf 'x86_64-apple-darwin 5f44dcbde809b632f47c36fadb241cb4d6f9af71d0c8f172b5d2026d3dde742c' ;;
        darwin-arm64) printf 'aarch64-apple-darwin a9c1b29002cf3c83f07fa9cd8a887a3be0107d90e23189721221e7257db8e3d6' ;;
    esac
}
UV="$PREFIX/uv/uv"
if [ ! -x "$UV" ] || [ "$("$UV" --version 2>/dev/null | cut -d' ' -f2)" != "$UV_VERSION" ]; then
    log "Installing uv $UV_VERSION"
    uv_info="$(uv_triple)"
    triple="${uv_info% *}"
    uv_sha="${uv_info#* }"
    fetch "${MVAULT_UV_BASE:-https://github.com/astral-sh/uv/releases/download/$UV_VERSION}/uv-$triple.tar.gz" "$TMP/uv.tar.gz" || die "could not download uv"
    [ "$(sha256_of "$TMP/uv.tar.gz")" = "$uv_sha" ] || die "checksum mismatch for uv"
    mkdir -p "$PREFIX/uv" "$TMP/uvx"
    tar -xzf "$TMP/uv.tar.gz" -C "$TMP/uvx"
    cp "$TMP/uvx/uv-$triple/uv" "$UV"
    chmod 755 "$UV"
fi
export UV_PYTHON_INSTALL_DIR="$PREFIX/python" UV_CACHE_DIR="$PREFIX/cache" UV_NO_PROGRESS=1 UV_PYTHON_PREFERENCE=only-managed UV_NO_CONFIG=1
log "Installing Python $PYTHON_VERSION and dependencies (this can take a minute)"
"$UV" python install --no-bin "$PYTHON_VERSION" >/dev/null
"$UV" venv --quiet --python "$PYTHON_VERSION" "$REL_DIR/venv"
"$UV" pip install --quiet --compile-bytecode --python "$REL_DIR/venv/bin/python" -r "$REL_DIR/requirements.txt"

# --- configuration (secrets are generated once and never overwritten) --------------------------------------------
FIRST_INSTALL=0
[ -f "$ENV_FILE" ] || FIRST_INSTALL=1
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"

ADMIN_PASSWORD_GENERATED=""
kv_put "$ENV_FILE" PORT "$PORT"
kv_put "$ENV_FILE" BIND_ADDRESS "$BIND"
kv_put "$ENV_FILE" GUNICORN_WORKERS 3
kv_put "$ENV_FILE" DJANGO_SECRET_KEY "$(rand_hex 48)"
kv_put "$ENV_FILE" MVAULT_ENCRYPTION_KEY "$(rand_hex 32)"
kv_put "$ENV_FILE" MVAULT_ENCRYPTION_SALT "$(rand_hex 32)"
if [ -n "$BASE_URL" ]; then
    kv_put "$ENV_FILE" MVAULT_BASE_URL "$BASE_URL"
elif [ "$FIRST_INSTALL" = 1 ]; then
    kv_put "$ENV_FILE" DJANGO_ALLOWED_HOSTS '*'
    warn "no --base-url given: accepting any Host header. Set it with: mvault config set MVAULT_BASE_URL https://your.domain"
fi
if [ "$FIRST_INSTALL" = 1 ]; then
    kv_put "$ENV_FILE" MVAULT_ADMIN_EMAIL "${ADMIN_EMAIL:-admin@mvault.local}"
    ADMIN_PASSWORD_GENERATED="$(rand_hex 12)"
    kv_put "$ENV_FILE" MVAULT_ADMIN_PASSWORD "$ADMIN_PASSWORD_GENERATED"
    kv_put "$ENV_FILE" MVAULT_ADMIN_MUST_CHANGE true
fi

# A re-run keeps the port and bind address already configured.
PORT="$(kv_get "$ENV_FILE" PORT)"
BIND="$(kv_get "$ENV_FILE" BIND_ADDRESS)"

# --- PostgreSQL ------------------------------------------------------------------------------------------------
PG_MODE=external
PG_BIN=""
as_postgres() {
    if have runuser; then runuser -u postgres -- "$@"; else su -s /bin/sh postgres -c "$(printf '%s ' "$@")"; fi
}
provision_role_and_db() { # provision_role_and_db <psql-runner...>  (password in $DB_PASSWORD)
    "$@" -v ON_ERROR_STOP=1 -v pw="$DB_PASSWORD" -d postgres -q <<'SQL'
SET password_encryption = 'scram-sha-256';
SELECT format('CREATE ROLE mvault LOGIN PASSWORD %L', :'pw') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mvault') \gexec
ALTER ROLE mvault WITH LOGIN PASSWORD :'pw';
SELECT 'CREATE DATABASE mvault OWNER mvault ENCODING ''UTF8'' TEMPLATE template0' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'mvault') \gexec
SQL
}

if [ "$WITH_POSTGRES" = 1 ]; then
    if [ "$MODE" = system ]; then
        PG_MODE=system
        if ! have psql || ! { have pg_isready || [ -d /usr/lib/postgresql ] || [ -d /var/lib/pgsql ]; }; then
            log "Installing PostgreSQL from the distribution packages"
            case " $(os_ids) " in
                *debian* | *ubuntu*)
                    export DEBIAN_FRONTEND=noninteractive
                    apt-get update -qq
                    apt-get install -y -qq postgresql postgresql-client >/dev/null
                    ;;
                *rhel* | *fedora* | *centos* | *rocky* | *almalinux*)
                    pkg=dnf; have dnf || pkg=yum
                    "$pkg" install -y -q postgresql-server postgresql-contrib >/dev/null
                    if [ ! -s /var/lib/pgsql/data/PG_VERSION ]; then
                        if have postgresql-setup; then postgresql-setup --initdb; else as_postgres initdb -D /var/lib/pgsql/data; fi
                    fi
                    ;;
                *) die "automatic PostgreSQL installation is not supported on '$(os_ids)'. Install PostgreSQL yourself and re-run with --database-url, or use --no-postgres." ;;
            esac
        fi
        if [ -d /run/systemd/system ] && { [ "$SYSTEMD" = 1 ] || [ "$START" = 1 ]; }; then
            systemctl enable --now postgresql >/dev/null 2>&1 || warn "could not enable/start postgresql.service"
        elif [ ! -d /run/systemd/system ]; then
            # No systemd (container/test): start the cluster directly so the database can be provisioned.
            service postgresql start >/dev/null 2>&1 || true
        fi
        i=0
        until as_postgres psql -qtAc 'select 1' >/dev/null 2>&1; do
            i=$((i + 1))
            [ "$i" -le 60 ] || die "PostgreSQL did not become ready (start it, then re-run this installer)"
            sleep 1
        done
        DB_PASSWORD="$(kv_get "$ENV_FILE" DB_PASSWORD)"
        [ -n "$DB_PASSWORD" ] || DB_PASSWORD="$(rand_hex 24)"
        log "Creating the PostgreSQL role and database 'mvault'"
        provision_role_and_db as_postgres psql
        # The distribution's default pg_hba.conf may only allow ident auth for 127.0.0.1 (RHEL family).
        hba="$(as_postgres psql -qtAc 'SHOW hba_file')"
        if [ -f "$hba" ] && ! grep -q '^host[[:space:]]\+mvault[[:space:]]\+mvault' "$hba"; then
            tmp_hba="$TMP/pg_hba.conf"
            { printf 'host mvault mvault 127.0.0.1/32 scram-sha-256\nhost mvault mvault ::1/128 scram-sha-256\n'; cat "$hba"; } >"$tmp_hba"
            cat "$tmp_hba" >"$hba"
            as_postgres psql -qtAc 'SELECT pg_reload_conf()' >/dev/null
        fi
        found_port="$(as_postgres psql -qtAc 'SHOW port')"
        kv_put "$ENV_FILE" DB_HOST 127.0.0.1
        kv_put "$ENV_FILE" DB_PORT "$found_port"
        kv_put "$ENV_FILE" DB_NAME mvault
        kv_put "$ENV_FILE" DB_USER mvault
        kv_put "$ENV_FILE" DB_PASSWORD "$DB_PASSWORD"
        PG_PORT="$found_port"
    else
        PG_MODE=brew
        if [ -n "${MVAULT_PG_BIN:-}" ]; then
            PG_BIN="$MVAULT_PG_BIN"
        elif [ -n "$EX_PG_BIN" ]; then
            PG_BIN="$EX_PG_BIN"
        else
            have brew || die "Homebrew is required for PostgreSQL on macOS (https://brew.sh). Or install PostgreSQL yourself and re-run with --database-url."
            brew list "$PG_BREW_FORMULA" >/dev/null 2>&1 || { log "Installing $PG_BREW_FORMULA with Homebrew"; brew install "$PG_BREW_FORMULA"; }
            PG_BIN="$(brew --prefix "$PG_BREW_FORMULA")/bin"
        fi
        [ -x "$PG_BIN/initdb" ] || die "PostgreSQL binaries not found in $PG_BIN"
        DB_PASSWORD="$(kv_get "$ENV_FILE" DB_PASSWORD)"
        [ -n "$DB_PASSWORD" ] || DB_PASSWORD="$(rand_hex 24)"
        PGDATA="$DATA_DIR/postgres"
        if [ ! -s "$PGDATA/PG_VERSION" ]; then
            log "Initialising a private PostgreSQL cluster in $PGDATA"
            printf '%s' "$DB_PASSWORD" >"$TMP/pwfile"
            "$PG_BIN/initdb" -D "$PGDATA" -U mvault -E UTF8 --auth-host=scram-sha-256 --auth-local=trust --pwfile="$TMP/pwfile" >/dev/null
        fi
        "$PG_BIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1 || "$PG_BIN/pg_ctl" -D "$PGDATA" -l "$DATA_DIR/logs/postgres.log" -w \
            -o "-p $PG_PORT -c listen_addresses=127.0.0.1 -c unix_socket_directories=''" start >/dev/null
        # TCP only: Unix socket paths are limited to 103 bytes on macOS and the data directory can be deeper.
        provision_role_and_db env "PGPASSWORD=$DB_PASSWORD" "$PG_BIN/psql" -h 127.0.0.1 -p "$PG_PORT" -U mvault
        kv_put "$ENV_FILE" DB_HOST 127.0.0.1
        kv_put "$ENV_FILE" DB_PORT "$PG_PORT"
        kv_put "$ENV_FILE" DB_NAME mvault
        kv_put "$ENV_FILE" DB_USER mvault
        kv_put "$ENV_FILE" DB_PASSWORD "$DB_PASSWORD"
    fi
else
    PG_MODE=external
    if [ "$MODE" = system ] && ! have pg_dump; then # client tools only: `mvault backup` and `restore` need pg_dump/pg_restore
        log "Installing the PostgreSQL client tools (for backups)"
        case " $(os_ids) " in
            *debian* | *ubuntu*)
                export DEBIAN_FRONTEND=noninteractive
                if apt-get update -qq && apt-get install -y -qq postgresql-client >/dev/null; then :; else warn "could not install postgresql-client; install it for 'mvault backup'"; fi
                ;;
            *rhel* | *fedora* | *centos* | *rocky* | *almalinux*)
                pkg=dnf; have dnf || pkg=yum
                if "$pkg" install -y -q postgresql >/dev/null; then :; else warn "could not install the PostgreSQL client; install it for 'mvault backup'"; fi
                ;;
        esac
    fi
    if [ "$FIRST_INSTALL" = 1 ]; then
        kv_put "$ENV_FILE" DATABASE_URL "$DATABASE_URL_ARG"
    fi
fi

# --- object storage ---------------------------------------------------------------------------------------------
MINIO_MODE=none
if [ "$WITH_STORAGE" = 1 ] && [ "$WITH_MINIO" = 1 ]; then
    MINIO_MODE=embedded
    log "Setting up MinIO"
    mkdir -p "$DATA_DIR/minio" "$DATA_DIR/minio-config" "$(dirname "$MINIO_BIN")"
    cp "$TMP/minio" "$MINIO_BIN.new"
    chmod 755 "$MINIO_BIN.new"
    mv -f "$MINIO_BIN.new" "$MINIO_BIN"
    S3_KEY="$(kv_get "$MINIO_ENV_FILE" MINIO_ROOT_USER)"
    S3_SECRET="$(kv_get "$MINIO_ENV_FILE" MINIO_ROOT_PASSWORD)"
    [ -n "$S3_KEY" ] || S3_KEY="$(rand_hex 12)"
    [ -n "$S3_SECRET" ] || S3_SECRET="$(rand_hex 24)"
    touch "$MINIO_ENV_FILE"
    chmod 600 "$MINIO_ENV_FILE"
    kv_put "$MINIO_ENV_FILE" MINIO_ROOT_USER "$S3_KEY"
    kv_put "$MINIO_ENV_FILE" MINIO_ROOT_PASSWORD "$S3_SECRET"
    kv_put "$MINIO_ENV_FILE" MINIO_VOLUMES "$DATA_DIR/minio"
    kv_put "$MINIO_ENV_FILE" MINIO_ADDRESS 127.0.0.1:9000
    kv_put "$MINIO_ENV_FILE" MINIO_BROWSER off
    kv_put "$ENV_FILE" S3_ENDPOINT_URL http://127.0.0.1:9000
    kv_put "$ENV_FILE" S3_ACCESS_KEY "$S3_KEY"
    kv_put "$ENV_FILE" S3_SECRET_KEY "$S3_SECRET"
    kv_put "$ENV_FILE" MVAULT_PROVISION_BUCKETS true
elif [ "$WITH_STORAGE" = 1 ]; then
    MINIO_MODE=external
    if [ "$FIRST_INSTALL" = 1 ]; then
        kv_put "$ENV_FILE" S3_ENDPOINT_URL "$S3_ENDPOINT_ARG"
        kv_put "$ENV_FILE" S3_ACCESS_KEY "$S3_KEY_ARG"
        kv_put "$ENV_FILE" S3_SECRET_KEY "$S3_SECRET_ARG"
        kv_put "$ENV_FILE" MVAULT_PROVISION_BUCKETS "${PROVISION_BUCKETS_ARG:-false}"
    fi
fi

# --- file ownership ----------------------------------------------------------------------------------------------
if [ "$MODE" = system ]; then
    chown root:mvault "$ENV_FILE"
    chmod 640 "$ENV_FILE"
    if [ -f "$MINIO_ENV_FILE" ]; then chown root:mvault "$MINIO_ENV_FILE"; chmod 640 "$MINIO_ENV_FILE"; fi
    chown -R root:root "$PREFIX"
    chmod -R a+rX "$PREFIX"
    [ "$MINIO_MODE" = embedded ] && chown -R mvault:mvault "$DATA_DIR/minio" "$DATA_DIR/minio-config"
fi

# --- layout file, CLI, units ----------------------------------------------------------------------------------------
{
    printf "MVAULT_MODE='%s'\nMVAULT_PREFIX='%s'\nMVAULT_CONF_DIR='%s'\nMVAULT_DATA_DIR='%s'\n" "$MODE" "$PREFIX" "$CONF_DIR" "$DATA_DIR"
    printf "MVAULT_PG_MODE='%s'\nMVAULT_PG_BIN='%s'\nMVAULT_PG_PORT='%s'\n" "$PG_MODE" "$PG_BIN" "$PG_PORT"
    printf "MVAULT_MINIO_MODE='%s'\nMVAULT_MINIO_BIN='%s'\nMVAULT_BIN_DIR='%s'\n" "$MINIO_MODE" "$MINIO_BIN" "$BIN_DIR"
} >"$TMP/layout.env"
cp "$TMP/layout.env" "$LAYOUT_FILE"
chmod 644 "$LAYOUT_FILE"
if [ "$MODE" = user ] && [ "$CONF_DIR" != "$HOME/Library/Application Support/mvault" ]; then
    mkdir -p "$HOME/.config/mvault"
    cp "$TMP/layout.env" "$HOME/.config/mvault/layout.env"
fi

mkdir -p "$BIN_DIR"
sed "s/__CLI_VERSION__/$VERSION/" "$REL_DIR/packaging/mvault" >"$BIN_DIR/mvault.new"
chmod 755 "$BIN_DIR/mvault.new"
mv -f "$BIN_DIR/mvault.new" "$BIN_DIR/mvault"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) warn "$BIN_DIR is not on your PATH; add it, e.g.: export PATH=\"$BIN_DIR:\$PATH\"" ;; esac

# Activate the release. (Not atomic, but the window is a few microseconds and services are about to restart.)
ln -sfn "$REL_DIR" "$PREFIX/current"

if [ "$MODE" = system ] && [ "$SYSTEMD" = 1 ]; then
    for unit in mvault-web mvault-minio; do
        [ "$unit" = mvault-minio ] && [ "$MINIO_MODE" != embedded ] && continue
        sed -e "s#@PREFIX@#$PREFIX#g" -e "s#@CONF_DIR@#$CONF_DIR#g" -e "s#@DATA_DIR@#$DATA_DIR#g" -e "s#@MINIO_BIN@#$MINIO_BIN#g" \
            "$REL_DIR/packaging/systemd/$unit.service" >"/etc/systemd/system/$unit.service"
        chmod 644 "/etc/systemd/system/$unit.service"
    done
    systemctl daemon-reload
    if [ "$MINIO_MODE" = embedded ]; then systemctl enable mvault-minio >/dev/null 2>&1; fi
    systemctl enable mvault-web >/dev/null 2>&1
fi

# --- start ----------------------------------------------------------------------------------------------------------------
prune_old_releases() {
    cur="$(cd "$PREFIX/current" && pwd -P)"
    # shellcheck disable=SC2012
    ls -1t "$PREFIX/releases" | tail -n +4 | while read -r old; do
        [ "$PREFIX/releases/$old" = "$cur" ] || rm -rf "${PREFIX:?}/releases/$old"
    done
}

if [ "$START" = 1 ]; then
    log "Starting services"
    if [ "$MODE" = system ]; then
        [ "$MINIO_MODE" = embedded ] && systemctl restart mvault-minio
        systemctl restart mvault-web
    else
        "$BIN_DIR/mvault" restart >/dev/null
    fi
    log "Waiting for mVault to answer"
    i=0
    until curl -fsS -o /dev/null --max-time 3 "http://127.0.0.1:$PORT/health/" 2>/dev/null; do
        i=$((i + 1))
        if [ "$i" -gt 120 ]; then
            if [ "$MODE" = system ]; then journalctl -u mvault-web -n 30 --no-pager >&2 || true; fi
            die "mVault did not become healthy within 2 minutes. Check: mvault logs"
        fi
        sleep 1
    done
    # The first administrator exists now; the one-time password no longer needs to stay in the config file.
    if [ -n "$ADMIN_PASSWORD_GENERATED" ] && grep -q '^MVAULT_ADMIN_PASSWORD=' "$ENV_FILE"; then
        if "$BIN_DIR/mvault" manage shell -c 'from mvault_app.models import User; raise SystemExit(0 if User.objects.filter(is_admin=True).exists() else 1)' >/dev/null 2>&1; then
            grep -v -e '^MVAULT_ADMIN_PASSWORD=' -e '^MVAULT_ADMIN_MUST_CHANGE=' "$ENV_FILE" >"$ENV_FILE.new"
            chmod --reference="$ENV_FILE" "$ENV_FILE.new" 2>/dev/null || chmod 600 "$ENV_FILE.new"
            [ "$MODE" = system ] && chown root:mvault "$ENV_FILE.new"
            mv -f "$ENV_FILE.new" "$ENV_FILE"
        fi
    fi
fi
prune_old_releases

# --- summary --------------------------------------------------------------------------------------------------------------
SHOWN_URL="$(kv_get "$ENV_FILE" MVAULT_BASE_URL)"
[ -n "$SHOWN_URL" ] || SHOWN_URL="http://localhost:$PORT"
if [ "$UPGRADE" = 1 ]; then
    printf '\n%smVault upgraded to %s.%s Open: %s\n' "$B" "$VERSION" "$R" "$SHOWN_URL"
    exit 0
fi
printf '\n%smVault %s is installed.%s\n\n' "$B" "$VERSION" "$R"
printf '  Open:      %s\n' "$SHOWN_URL"
if [ -n "$ADMIN_PASSWORD_GENERATED" ]; then
    printf '  Sign in:   %s\n  Password:  %s   (shown only once; you must change it at first sign-in)\n\n' "$(kv_get "$ENV_FILE" MVAULT_ADMIN_EMAIL || echo "${ADMIN_EMAIL:-admin@mvault.local}")" "$ADMIN_PASSWORD_GENERATED"
    printf '  Important: back up %s (it holds your encryption key and salt). Without them stored data cannot be decrypted.\n\n' "$ENV_FILE"
fi
if [ "$MODE" = system ]; then
    if [ "$SYSTEMD" = 1 ]; then printf '  Services are enabled and start at boot. '; fi
    printf 'Manage them with: mvault status | start | stop | restart | logs | backup | upgrade\n'
else
    printf '  mVault does not start automatically on macOS. Use: mvault start | stop | restart | status | logs\n'
    [ "$START" = 1 ] || printf '  Start it now with: mvault start\n'
fi
printf '  Put a reverse proxy (Caddy, nginx, Traefik, NPM...) with HTTPS in front for anything beyond localhost.\n'
