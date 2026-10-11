# Troubleshooting

First step, always: `docker logs mvault` (or your service logs), then `manage.py check_config`.

## Running manage.py in the all-in-one image

Secrets and generated settings live in s6's container environment, not in the plain Docker environment, so a bare `docker exec … python manage.py …` fails with *Set DJANGO_SECRET_KEY…*. Use `with-contenv` and run as the app user *(untested)*:

```bash
docker exec -it mvault /command/with-contenv sh -c 'cd /app && /command/s6-setuidgid mvault python manage.py check_config'
```

Replace `check_config` with any command (`rotate_encryption_key`, `changepassword you@example.com`, …). In the slim image just `docker exec -it mvault python manage.py check_config`.

## Symptoms

| Symptom | Likely cause and fix |
|---|---|
| **400 Bad Request** on every page | Host not allowed. Set `MVAULT_BASE_URL` to the exact public URL (or add the name to `DJANGO_ALLOWED_HOSTS`). |
| **403 "CSRF verification failed"** behind a proxy | `MVAULT_BASE_URL` missing/wrong, or the proxy does not send `X-Forwarded-Proto: https` / the real `Host`. See [Reverse proxy](reverse-proxy.md). |
| Sign-in works but you are bounced back to the login page | Secure cookies over plain HTTP. Use HTTPS, or set `SESSION_COOKIE_SECURE=false` (HTTP/LAN only). |
| **429** "Too many failed sign-in attempts" | Throttled; wait `MVAULT_LOGIN_WINDOW_SECONDS` (15 min default). Behind a proxy make sure `X-Forwarded-For` is set so one user does not lock everyone out. |
| **413** or a failed upload | Proxy body limit. Allow ≥ 55 MB (`client_max_body_size 55m;`). |
| **502/504** during upload/download | Proxy timeout too low; use ≥ 120 s. |
| *"File storage is not configured on this server."* | `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` are not all set. Check with `check_config`. |
| *"Could not store the file / icon / image"* | Storage unreachable or bucket missing or the key lacks permission. `check_config` lists each bucket; create buckets or run `provision_storage`. |
| Icons/avatars show as broken images | They are served at `/media/…` to signed-in users only; check the app can read the bucket. If you set `ICONS_PUBLIC_BASE_URL`/`AVATARS_PUBLIC_BASE_URL` the browser must reach that URL and the bucket must allow anonymous `GetObject` ([Installation](installation.md#22-minio)). Clear stale DNS caches for new hostnames. |
| The *File* record type is missing | Object storage is not configured. |
| *"Stored value could not be decrypted; check the encryption key and salt."* | `MVAULT_ENCRYPTION_KEY`/`SALT` differ from the ones the data was written with. Restore the original values (or run a rotation if you know both). |
| *ImproperlyConfigured: Set DJANGO_SECRET_KEY / MVAULT_ENCRYPTION_KEY…* | A required secret is missing. In the all-in-one image with an external database, supply the encryption key and salt yourself. |
| Container exits at start with *Set MVAULT_ADMIN_PASSWORD to initialize the administrator* | No admin exists with `MVAULT_ADMIN_EMAIL` and no password was given. Set `MVAULT_ADMIN_PASSWORD` (or the e-mail of your existing admin). |
| *Database did not become ready* | Wrong host/credentials/network. Test with `psql "$DATABASE_URL"`. |
| After upgrading from 0.3.x a new admin appears or storage disappeared | Defaults changed; see [Upgrading](upgrading.md#upgrading-from-03x-homelab--pre-release-deployments-to-04). |
| Forgot the administrator password | Run `changepassword` for that e-mail (see above) *(untested)*. Members' passwords can be reset by the administrator in the UI. |

## Health check

`GET /health/` returns `ok` without signing in. The image `HEALTHCHECK` uses it on port 8000.

## Getting help

Open an issue using the *Installation / configuration help* template. **Never paste secrets** (keys, passwords, `.env` contents, database URLs with passwords); redact them. For security problems use a [private advisory](https://github.com/orkhan/mvault/security/advisories/new).
