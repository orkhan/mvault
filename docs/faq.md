# FAQ

**What is mVault, in one line?** A small self-hosted vault for a family or a few people: logins, cards, secrets, JSON and files, organised in projects and folders and encrypted at rest.

**How is it different from Vaultwarden or Bitwarden?** Those are full password managers with browser extensions, mobile apps and end-to-end encryption. mVault has none of that. It is a web app organised around projects and folders that also holds env variables, JSON documents and files. Choose Vaultwarden/Bitwarden if you want autofill; choose mVault if you want a simple, readable, self-contained store you can reason about.

**Is it end-to-end encrypted?** No. Values are encrypted in the database with a key the server holds, so the server operator is trusted. See [Security](security.md).

**Is it audited?** No.

**Is there a browser extension, mobile app, TOTP, or SSO?** No. The interface is responsive web. Two-factor sign-in and importers are ideas, not commitments.

**Do I need MinIO?** No. Without S3-compatible storage mVault runs fine; icons, avatars and file records are simply unavailable. With the all-in-one image MinIO is embedded; elsewhere point `S3_*` at MinIO, Ceph, R2, B2 or similar.

**Can I use my existing PostgreSQL?** Yes, 14 or newer. Set `DATABASE_URL` (or `DB_*`). The all-in-one image then skips its embedded PostgreSQL.

**Where is my data?** All-in-one: the `/data` volume. Otherwise in your PostgreSQL and your buckets. Nothing is sent anywhere, except that browsers may ask gravatar.com for an avatar (SHA-256 of the e-mail) when no avatar was uploaded.

**Can people sign up themselves?** No. The administrator creates accounts.

**Can the administrator read my records?** Not through the app: the administrator account has no vault. An operator with access to the server, database and key could, as with any self-hosted app.

**What happens if I lose the encryption key?** The encrypted values are unrecoverable. Back up key and salt separately ([Backup & restore](backup-restore.md)).

**Can I change the key?** Yes, with `manage.py rotate_encryption_key` ([Security](security.md#rotating-the-key)).

**Which proxy should I use?** Any. See [Reverse proxy](reverse-proxy.md).

**Which languages?** English and Russian, chosen per member in Settings.

**Can I get my data out?** Yes: *Settings → Export all data* gives a ZIP with a CSV of decrypted values per folder and your files. A plain `.env` export exists per environment folder in secret projects.

**Which platforms?** Docker images are planned for amd64 and arm64. The native installer targets Linux and macOS. See the [install options](installation.md).

**Can I contribute?** Please do: [CONTRIBUTING.md](../CONTRIBUTING.md).
