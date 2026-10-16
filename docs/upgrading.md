# Upgrading

mVault follows semantic-ish versioning while it is pre-1.0: minor versions (0.x) may include changes you need to act on; read the [CHANGELOG](../CHANGELOG.md) before upgrading.

## Routine upgrade (Docker)

1. **Back up** the database, object storage and keys ([Backup & restore](backup-restore.md)).
2. Read the changelog entries between your version and the target.
3. Pull and recreate:

   ```bash
   docker compose pull && docker compose up -d       # compose.yaml / compose.external.yaml
   # or: docker pull ghcr.io/orkhan/mvault:<version> && recreate the container with the same volume and variables
   ```

4. Migrations run automatically at start. Watch `docker logs mvault`; the container is healthy once `/health/` answers.
5. Run `manage.py check_config` and sign in.

Pin a specific version tag in production (`:0.4.0`) instead of `:latest`, so upgrades are deliberate. The all-in-one image embeds PostgreSQL 15; a future image that changes the PostgreSQL major version will need a dump/restore, and its release notes will say so.

**Downgrading is not supported.** If an upgrade fails, restore the backup and start the previous image.

## Upgrading to 0.6.0

This release adds the optional Chrome extension and its authenticated endpoints. It has no database migration. Update the mVault app before connecting the extension; older servers do not provide the extension API.

## Upgrading from 0.3.x (homelab / pre-release deployments) to 0.4

0.4 makes the app configurable for everyone, which changed some defaults that used to be deployment-specific. If you ran the 0.2/0.3 compose files, set these **before** starting the new image:

| What changed | What to do |
|---|---|
| The administrator e-mail was fixed in code; it is now `MVAULT_ADMIN_EMAIL` (default `admin@mvault.local`). | Set `MVAULT_ADMIN_EMAIL` to your **existing** admin address. If you do not, startup looks for the default address, finds none, and either exits (no `MVAULT_ADMIN_PASSWORD`) or creates a second administrator. |
| `S3_ENDPOINT_URL` had a default (`http://minio:9000`); it is now empty. | Set `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` explicitly or storage is treated as not configured (icons/avatars/files unavailable). |
| Icon/avatar public URLs had a deployment default. | Icons and avatars are now served by the app at `/media/…` by default. To keep using public buckets, set `ICONS_PUBLIC_BASE_URL` and `AVATARS_PUBLIC_BASE_URL`. |
| Secure cookies were on by default; now they follow `MVAULT_BASE_URL`. | Set `MVAULT_BASE_URL=https://…` (or keep `SESSION_COOKIE_SECURE=true`). Hosts and CSRF origins derive from it as well. |
| `DB_HOST` defaulted to `postgresql`; now `localhost`. | Set `DB_HOST` or `DATABASE_URL`. |
| The time zone was `Asia/Baku`; now `UTC`. | Set `MVAULT_TIME_ZONE` (or `TZ`) if you want local times. |
| New: sign-in throttling, Content-Security-Policy, `MVAULT_TRUST_PROXY`. | No action; set `MVAULT_TRUST_PROXY=false` only if no proxy sits in front. |

Your encryption key and salt carry over unchanged. Database migrations for this release are additive (`LoginAttempt` table).

## Key rotation

Not part of routine upgrades; see [Security](security.md#rotating-the-key).


## PostgreSQL major versions in the all-in-one image

Each image line pins one PostgreSQL major version (0.4.x uses **PostgreSQL 15**). A future image that ships a newer major will say so in its release notes, and it **refuses to start** on a data directory written by a different major (it logs a clear error instead of touching the data). To move to it, dump from the old image and restore into a fresh volume on the new one *(untested until the first major change; the commands match [Backup and restore](backup-restore.md))*:

```bash
# 1. With the OLD image still running, take a logical dump and copy your secrets
docker exec -u postgres mvault /usr/lib/postgresql/15/bin/pg_dump -h /run/postgresql -U mvault -Fc mvault > mvault.dump
docker cp mvault:/data/config/secrets.env ./secrets.env      # holds the encryption key and salt

# 2. Start the NEW image on an empty volume, put secrets.env into /data/config/ before first start, then restore
docker run -d --name mvault-new -v mvault-data-new:/data ... ghcr.io/orkhan/mvault:<new-version>
docker exec -i -u postgres mvault-new pg_restore -h /run/postgresql -U mvault -d mvault --clean --if-exists < mvault.dump
```

If you would rather not repeat this, use an external PostgreSQL (the `slim` image) and upgrade it with your own tooling.
