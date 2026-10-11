# Native installer (Linux and macOS)

`install.sh` (repository root) installs mVault without Docker: PostgreSQL, MinIO and the app on the host. It is
meant to be piped to a shell and is safe to re-run (a re-run is an upgrade; secrets are never overwritten).

```sh
curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/install.sh | sudo sh    # Linux (systemd)
curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/install.sh | sh         # macOS
```

| File | Purpose |
|---|---|
| `mvault` | The `mvault` command (bash): `start stop restart status logs enable disable config admin manage backup restore upgrade doctor uninstall version`. Installed to `/usr/local/bin` (macOS: `~/.local/bin` when `/usr/local/bin` is not writable). |
| `systemd/mvault-web.service`, `systemd/mvault-minio.service` | Hardened units with `@PREFIX@`, `@CONF_DIR@`, `@DATA_DIR@`, `@MINIO_BIN@` placeholders that the installer substitutes. |
| `test/make-release-dir.sh` | Assembles a release directory (app tarball, MinIO binaries, `SHA256SUMS`, `install.sh`) so the installer can be tested offline with `MVAULT_RELEASE_BASE`. |

## Release assets the installer expects

At `https://github.com/orkhan/mvault/releases/download/vX.Y.Z/`: `mvault-X.Y.Z-app.tar.gz` (top-level directory
`mvault-X.Y.Z/` with `manage.py`, `mvault_app/`, `mvault_project/`, `requirements.txt`, `packaging/`, `LICENSE`),
`minio-{linux,darwin}-{amd64,arm64}`, `install.sh`, and `SHA256SUMS` covering every asset. Everything is verified
against `SHA256SUMS`; `uv` (pinned, checksum-verified in the script) provides a managed Python 3.12.

## Layout

| | Linux (system) | macOS (user) |
|---|---|---|
| Application | `/opt/mvault/releases/<version>` + `current` symlink | `<base>/app/releases/<version>` + `current` |
| Configuration | `/etc/mvault/{mvault.env,minio.env,layout.env}` | `<base>/{mvault.env,minio.env,layout.env}` |
| Data | `/var/lib/mvault` (`minio/`, `backups/`, `logs/`) | `<base>/data` (adds `postgres/`) |
| PostgreSQL | distro packages, role/db `mvault`, localhost | Homebrew `postgresql@17`, private cluster on port 54329, TCP only |
| Services | `mvault-web`, `mvault-minio` (+ `postgresql`), enabled at boot | processes managed by `mvault start/stop`, no auto-start |

`<base>` is `~/Library/Application Support/mvault` unless `--prefix` is given. `layout.env` records the mode, paths and
which components are embedded; the CLI reads it. Linux only: `--prefix` moves just the application directory.

## Testing

`packaging/test/make-release-dir.sh 0.0.0-test /tmp/rel path/to/minio-linux-amd64` then
`MVAULT_RELEASE_BASE=/tmp/rel sh install.sh --version 0.0.0-test --yes`. systemd works inside a privileged container
(for example `jrei/systemd-debian:12`), which allows testing the units, reboot persistence, upgrade and rollback.
Lint with `shellcheck -s sh install.sh` and `shellcheck -x -s bash packaging/mvault`.
