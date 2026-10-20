# Security

mVault protects a family's secrets at a practical level for self-hosting. This page says what it does and where its limits are. **It has not been independently audited.**

## What encryption at rest covers

Before a value is written to PostgreSQL it is encrypted with AES-256-GCM (a fresh random nonce per value, ciphertext stored as `enc:v1:<base64>`). Covered:

- `Record.data` – every field of every record (passwords, card numbers, JSON, notes, …)
- `RecordRevision.snapshot` – the history of every record
- `Attachment.meta` – file names and content types

The 256-bit key is derived with scrypt from two secrets you control, `MVAULT_ENCRYPTION_KEY` and `MVAULT_ENCRYPTION_SALT`. Result: a stolen database dump, a leaked backup or a disk image **without** those secrets contains ciphertext, not secrets.

## What it does not cover

- **A compromised running server.** The key must be available to the app to decrypt values for display, so anyone who controls the application process, its environment or its host can read everything. This is not end-to-end encryption and the server operator is trusted.
- **Plaintext metadata:** record titles/keys, project and folder names, member names and e-mail addresses, the audit log, timestamps, file sizes and checksums.
- **File contents.** Files are stored as-is in the **private** `mvault-attachments` bucket and streamed through the app after access checks; they are not separately encrypted. Protect the storage with disk encryption and keep the bucket private. Icons and avatars are images you chose to upload.
- **Plain-text exports.** *Export all data* produces decrypted CSVs; delete them after use.
- **The administrator** has no vault and cannot open records through the app, but an administrator who also controls the server can read the database and key like any operator.
- **Clients.** A device with an unlocked browser session sees what you see; shared computers need care.

## Keys and backups

- Generate the key and salt with `openssl rand -hex 32` each.
- **Back them up separately** from the database/volume backup (a password manager other than mVault is fine). If you lose them, the encrypted values cannot be recovered.
- Do not change them casually: changing either one makes existing data undecryptable until you restore the old values or run a rotation.
- In the all-in-one image the generated key is stored in `/data/config/secrets.env`, inside the data volume, so **volume backups contain the key next to the data**. For backups that are ciphertext-only, pass your own `MVAULT_ENCRYPTION_KEY`/`MVAULT_ENCRYPTION_SALT` (they are then not written to the volume) and store them elsewhere.
- With an external database the all-in-one image refuses to generate a key for you for the same reason.

## Rotating the key

`manage.py rotate_encryption_key` re-encrypts every stored value from an old key/salt to a new one inside a single transaction. It stops without changes if the old values are wrong.

1. Stop the application and **back up the database**.
2. Set the new values in `MVAULT_ENCRYPTION_KEY`/`MVAULT_ENCRYPTION_SALT` and the previous ones in `OLD_MVAULT_ENCRYPTION_KEY`/`OLD_MVAULT_ENCRYPTION_SALT`.
3. Run `python manage.py rotate_encryption_key --dry-run`, then without `--dry-run`. (In the all-in-one image see [Troubleshooting](troubleshooting.md#running-managepy-in-the-all-in-one-image) for how to run commands.)
4. Remove the `OLD_*` variables and start the application.

Old backups remain protected by the old key; keep it until you retire them.

## Accounts and sessions

- Passwords are hashed with Argon2id (PBKDF2 as fallback). Minimum length 12 plus Django's common-password and similarity validators.
- Accounts are created only by the administrator; new and reset passwords must be changed at next sign-in.
- **Sign-in throttling:** after `MVAULT_LOGIN_MAX_ATTEMPTS` (default 5) failed attempts for an e-mail within `MVAULT_LOGIN_WINDOW_SECONDS` (default 15 minutes), sign-in is refused with HTTP 429; the per-address limit is four times that. Throttling uses the rightmost `X-Forwarded-For` entry when `MVAULT_TRUST_PROXY` is on. There is no two-factor sign-in yet.
- Masked values are revealed or copied only on request; those actions are audited. Shares are read-only and revoked automatically when an account is deactivated or deleted.
- The Chrome extension uses the existing signed-in browser session; there is no extension token. It lists names and usernames for all accessible exact-host password matches, but returns a password only after the user selects a record. It rechecks access and hostname on the server and disables response caching. The extension itself can read filled credentials in the browser; install only reviewed copies.
- Saving from the extension (`/extension/save-check/`, `/extension/save/`) is member-only, CSRF-protected and owner-only: it can create password records in the member's own password projects and change the password of the member's own matching record (the old value stays in record history). The check endpoint compares a captured password with stored ones in constant time and stores, logs and echoes nothing; saves and updates are audited with the hostname only. The browser extension keeps a captured password only in `chrome.storage.session` (memory, not visible to web pages) for about a minute. See [Chrome extension](chrome-extension.md).

## Web hardening

- **Content-Security-Policy** (`default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`, restricted `img-src` that includes Gravatar and your public icon URLs). The templates still use inline scripts and styles, so `'unsafe-inline'` remains for those two directives; this limits what an injected tag can load but is not a strict CSP.
- Secure, HttpOnly, SameSite=Lax cookies; HSTS when `MVAULT_BASE_URL` is HTTPS; `X-Content-Type-Options: nosniff`; `X-Frame-Options: DENY`; `Referrer-Policy: same-origin`.
- Uploads: images are decoded, validated and re-encoded to PNG (EXIF and other metadata dropped); attachments are served with `Content-Disposition: attachment` and `Cache-Control: no-store`.
- Avatars query Gravatar from the **browser** using a SHA-256 hash of the member's e-mail address. If you do not want that, give members an uploaded avatar (an uploaded one is always used first).

## Reporting a vulnerability

Please report privately: <https://github.com/orkhan/mvault/security/advisories/new>. See [SECURITY.md](../SECURITY.md). Do not post secrets or exploit details in public issues.
