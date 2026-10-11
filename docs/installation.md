# Installation

mVault installs in four ways. Pick one; they all run the same application.

| Path | Section |
|---|---|
| Docker, everything in one container | [1](#1-docker-all-in-one) |
| Docker, app only, your own PostgreSQL and MinIO/S3 | [2](#2-docker-slim-with-your-own-postgresql-and-minio) |
| Mixed: embedded PostgreSQL + your MinIO (or the reverse) | [3](#3-mixing-embedded-and-external-parts) |
| Native Linux / macOS, Proxmox LXC | [4](#4-native-linux-macos-and-proxmox-lxc) |

> **Verification status (read this first).** The container images are published with **v0.4.0**; before then use [building from source](development.md). Commands below that were run against the real application are not marked; commands that rely on the not-yet-published images, or that I could not run, are marked *(untested)*. The MinIO provisioning commands in section 2 are the ones used in the maintainer's homelab.

## Image tags

| Tag | Image |
|---|---|
| `X.Y.Z`, `X.Y`, `latest` | all-in-one |
| `X.Y.Z-slim`, `X.Y-slim`, `latest-slim` | slim (app only) |
| `edge`, `edge-slim` | latest `main`, for testing only |

All are multi-arch (`linux/amd64`, `linux/arm64`). Pin an exact version in production.

## What you need

- A host that runs Docker (amd64 or arm64), for sections 1–3.
- A way to serve mVault over HTTPS. A reverse proxy is **not** included; see [Reverse proxy](reverse-proxy.md). For a quick look on a LAN you can use plain HTTP.
- Somewhere safe, outside mVault, to keep the encryption key and salt ([Backup & restore](backup-restore.md)).

## 1. Docker all-in-one

One container runs the app, PostgreSQL 15 and MinIO under [s6-overlay](https://github.com/just-containers/s6-overlay). Everything lives in the `/data` volume.

```bash
docker run -d --name mvault --restart unless-stopped -p 8000:8000 \
  -v mvault-data:/data \
  -e MVAULT_BASE_URL=https://vault.example.com \
  -e MVAULT_ADMIN_EMAIL=you@example.com \
  ghcr.io/orkhan/mvault:latest          # (untested until v0.4.0 images exist)
```

Or with Compose, using the file in this repository:

```bash
docker compose up -d                    # (untested until v0.4.0 images exist)
```

First start:

1. The container generates secrets into `/data/config/secrets.env` (Django secret key, encryption key and salt, database and MinIO passwords). Values you pass yourself as environment variables win and are **not** written to that file.
2. If you did not set `MVAULT_ADMIN_PASSWORD`, a password is generated and printed once in the log. View it with `docker logs mvault`. You must change it at first sign-in.
3. PostgreSQL is initialised in `/data/postgres`, MinIO stores files in `/data/minio`, buckets are created, migrations run, and gunicorn listens on port **8000**.

Notes:

- Set `MVAULT_BASE_URL` to the address people will actually type. If you leave it unset the container accepts any `Host` header and logs a warning; that is only meant for a first look.
- With plain HTTP (`http://…`) cookies are not marked `Secure`. Use HTTPS in front before real use.
- To keep encryption keys **out** of the data volume (so volume backups are ciphertext-only), supply `MVAULT_ENCRYPTION_KEY` and `MVAULT_ENCRYPTION_SALT` yourself ([Security](security.md#keys-and-backups)).
- Running management commands in this image needs the container environment that s6 manages; use the bundled wrapper: `docker exec -it mvault mvault-manage <command>` (see [Troubleshooting](troubleshooting.md#running-managepy-in-the-all-in-one-image)).

## 2. Docker slim with your own PostgreSQL and MinIO

The `-slim` image contains only the app. You supply the database and, optionally, S3-compatible storage. It does not generate secrets: set them in `.env`.

### 2.1 PostgreSQL (14 or newer)

```sql
CREATE ROLE mvault LOGIN PASSWORD 'choose-a-strong-password';
CREATE DATABASE mvault OWNER mvault ENCODING 'UTF8';
```

The app runs its own migrations, so the role only needs to own that database.

### 2.2 MinIO

mVault uses three buckets. All can stay **private**: the app serves icons and avatars itself at `/media/…` to signed-in users, and streams file downloads after its access checks.

| Bucket (default name) | Holds |
|---|---|
| `mvault-icons` | project and folder icons |
| `mvault-avatars` | member avatars |
| `mvault-attachments` | files of file records |

Create the buckets and a least-privilege service account with the [MinIO client](https://min.io/docs/minio/linux/reference/minio-mc.html) (idempotent; these are the commands used in the maintainer's homelab):

```bash
mc alias set myminio https://minio.example.lan:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing myminio/mvault-icons myminio/mvault-avatars myminio/mvault-attachments
mc anonymous set none myminio/mvault-attachments

cat > mvault-app.json <<'JSON'
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["s3:ListBucket","s3:GetBucketLocation"],
  "Resource":["arn:aws:s3:::mvault-icons","arn:aws:s3:::mvault-avatars","arn:aws:s3:::mvault-attachments"]},
 {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject"],
  "Resource":["arn:aws:s3:::mvault-icons/*","arn:aws:s3:::mvault-avatars/*","arn:aws:s3:::mvault-attachments/*"]}
]}
JSON
mc admin policy create myminio mvault-app mvault-app.json
mc admin user add myminio mvault-app 'choose-a-long-random-secret'
mc admin policy attach myminio mvault-app --user mvault-app
```

Optional **public-icon mode**: if you prefer browsers to load icons and avatars straight from MinIO (for example through your proxy), make those two buckets anonymously readable for objects only and set `ICONS_PUBLIC_BASE_URL` / `AVATARS_PUBLIC_BASE_URL`:

```bash
for b in mvault-icons mvault-avatars; do
cat > "$b-public.json" <<JSON
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"AWS":["*"]},"Action":["s3:GetObject"],"Resource":["arn:aws:s3:::$b/*"]}]}
JSON
mc anonymous set-json "$b-public.json" "myminio/$b"
done
```

Prefer not to create buckets by hand? Give the service account `s3:CreateBucket` and set `MVAULT_PROVISION_BUCKETS=true`; the container then creates missing buckets at start *(untested)*.

### 2.3 Plain S3 (AWS S3, Cloudflare R2, Backblaze B2, Ceph, …)

Create the same three buckets and an access key whose policy is the JSON above (replace the ARNs with your bucket ARNs). Then set:

```env
S3_ENDPOINT_URL=https://s3.eu-central-1.amazonaws.com
S3_REGION=eu-central-1
S3_ACCESS_KEY=…
S3_SECRET_KEY=…
```

mVault addresses buckets path-style (`https://host/bucket/key`), which MinIO, Ceph, R2 and B2 accept. AWS S3 is deprecating path-style for new buckets, so prefer MinIO-compatible stores. *(Not tested against AWS.)*

### 2.4 Configure and start

```bash
cp .env.example .env
# fill in: MVAULT_BASE_URL, DJANGO_SECRET_KEY, MVAULT_ENCRYPTION_KEY, MVAULT_ENCRYPTION_SALT,
#          MVAULT_ADMIN_EMAIL, MVAULT_ADMIN_PASSWORD, DATABASE_URL, S3_*
docker compose -f compose.external.yaml up -d      # (untested until v0.4.0 images exist)
```

Generate secrets with `openssl rand -hex 32` (`-hex 48` for `DJANGO_SECRET_KEY`). The container waits for the database, migrates, creates the first administrator, and serves on port 8000. If it exits immediately, read `docker logs mvault`: missing secrets and a missing admin password are reported by name.

If your PostgreSQL or MinIO run in Docker on the same host, attach mVault to their network (see the commented lines in `compose.external.yaml`) and use the container names as hosts.

**No object storage?** Leave `S3_*` empty. mVault works without it; icon, avatar and file uploads are disabled and the *File* record type is hidden.

## 3. Mixing embedded and external parts

With the all-in-one image, the embedded component is skipped automatically when you set the matching variables:

| You set | Embedded part skipped |
|---|---|
| `DB_HOST` or `DATABASE_URL` | PostgreSQL |
| `S3_ENDPOINT_URL` (or `MVAULT_STORAGE=disabled` to turn storage off) | MinIO |

Example: embedded PostgreSQL, your own MinIO:

```bash
docker run -d --name mvault -p 8000:8000 -v mvault-data:/data \
  -e MVAULT_BASE_URL=https://vault.example.com \
  -e S3_ENDPOINT_URL=https://minio.example.lan:9000 \
  -e S3_ACCESS_KEY=mvault-app -e S3_SECRET_KEY=… \
  ghcr.io/orkhan/mvault:latest                      # (untested until v0.4.0 images exist)
```

With an **external database** the all-in-one image refuses to invent an encryption key (a key stored on a volume that can be lost while the database survives would make your data unreadable). Provide `MVAULT_ENCRYPTION_KEY` and `MVAULT_ENCRYPTION_SALT`, or set `MVAULT_AUTO_GENERATE_SECRETS=true` if you accept that risk.

## 4. Native Linux, macOS and Proxmox LXC

A Docker-free installer (`curl … | sh`, systemd on Linux, a `mvault` command on macOS) and a Proxmox helper script are planned for **v0.4.0**. See [native-install.md](native-install.md) and [proxmox.md](proxmox.md).

## After installing

1. Put HTTPS in front ([Reverse proxy](reverse-proxy.md)) and set `MVAULT_BASE_URL` to the `https://` address.
2. Sign in as the administrator, change the password, and create member accounts (members get *Passwords* and *Bank Cards* projects automatically).
3. Back up the data **and** the key ([Backup & restore](backup-restore.md)).
4. Run `manage.py check_config` for a quick health report ([Troubleshooting](troubleshooting.md)).
