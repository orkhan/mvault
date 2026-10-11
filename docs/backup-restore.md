# Backup and restore

You need to back up **three things**, and they are only useful together:

1. **The database** – all projects, folders, records (encrypted values), history, accounts.
2. **The object storage** – icons, avatars and the files of file records.
3. **The encryption key and salt** (`MVAULT_ENCRYPTION_KEY`, `MVAULT_ENCRYPTION_SALT`) – without them the encrypted values in a restored database are unreadable. Store them somewhere that is *not* mVault and *not* only inside the same backup (see [Keys and backups](security.md#keys-and-backups)).

> **Verification status.** The commands below use standard tools but were **not** all run against a published image; they are marked *(untested)* where relevant. Test a restore before you need one.

## Docker all-in-one

Everything (database, files, `/data/config/secrets.env`) is in the `/data` volume.

**Simple, consistent: stop, copy, start** *(untested)*

```bash
docker stop mvault
docker run --rm -v mvault-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/mvault-data-$(date +%F).tar.gz -C /data .
docker start mvault
```

The archive contains `/data/config/secrets.env`, which holds the generated encryption key **next to the data**. Treat the archive as secret. If you want backups that are ciphertext-only, supply `MVAULT_ENCRYPTION_KEY`/`MVAULT_ENCRYPTION_SALT` yourself (they then are not written to the volume) and keep them separately.

**Logical database dump while running** *(untested)*

```bash
docker exec -u postgres mvault /usr/lib/postgresql/15/bin/pg_dump \
  -h /run/postgresql -U mvault -Fc mvault > mvault-$(date +%F).dump
```

This captures the database only; copy `/data/minio` as well (best with the container stopped) for icons, avatars and files.

**Restore** *(untested)*: create a fresh container with the same `MVAULT_ENCRYPTION_*` values, stop it, replace the volume contents with the archive (`tar xzf … -C /data` into an empty volume), and start it. Migrations run at start.

## Docker slim / external PostgreSQL and MinIO

1. **Database** *(standard PostgreSQL tooling)*:

   ```bash
   pg_dump -Fc -h postgres.example.lan -U mvault mvault > mvault-$(date +%F).dump
   ```

2. **Object storage** (MinIO client):

   ```bash
   mc mirror --overwrite myminio/mvault-attachments backup/mvault-attachments
   mc mirror --overwrite myminio/mvault-icons       backup/mvault-icons
   mc mirror --overwrite myminio/mvault-avatars     backup/mvault-avatars
   ```

   Icons and avatars are low value (they are re-uploadable); the attachments bucket matters.

3. **Keys and `.env`** – copy the encryption key and salt to your password manager.

Take the database dump and the bucket copy close together in time. A file record whose object is missing shows an error on download; an object without a database row is just unused space.

### Restore

1. Create an empty database and role (`CREATE ROLE`, `CREATE DATABASE … OWNER mvault`).
2. `pg_restore -h … -U mvault -d mvault --no-owner mvault-YYYY-MM-DD.dump`
3. Restore the buckets (`mc mirror --overwrite backup/mvault-attachments myminio/mvault-attachments`, and so on).
4. Start mVault with the **same** `MVAULT_ENCRYPTION_KEY` and `MVAULT_ENCRYPTION_SALT`. If they differ, values show a decryption error instead of data.
5. Run `manage.py check_config`.

## Native installs

Planned for v0.4.0 together with a `mvault backup` / `mvault restore` command; see [native-install.md](native-install.md).

## Practical advice

- Automate it (cron/systemd timer) and **keep at least one copy off the machine**.
- Encrypt backup archives that contain secrets, and rotate old ones.
- Exports from *Settings → Export all data* are **not** a backup: they are plain-text copies for a single member's data. Delete them after use.
- Do a restore drill on a scratch machine once.
