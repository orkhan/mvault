# Proxmox VE LXC

Run mVault in its own Debian LXC on Proxmox VE, **without Docker**. The helper creates the container and installs PostgreSQL, MinIO and mVault inside it using the same [native installer](native-install.md) as any Linux machine, so the layout, systemd services and the `mvault` command are identical.

> **Status:** the scripts are written and syntax-checked, but have **not yet been run on a real Proxmox host** (see [Testing](#testing)). They follow the [community-scripts](https://community-scripts.org/) framework; submission there is a separate, later step.

## Create the container

Run this on the **Proxmox host** shell (as root):

```bash
COMMUNITY_SCRIPTS_URL=https://raw.githubusercontent.com/orkhan/mvault/main/proxmox \
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/proxmox/ct/mvault.sh)"
```

The framework's menu lets you accept the defaults or customise the container. Defaults: Debian 13, unprivileged, 2 vCPU, 2 GB RAM, 8 GB disk (the image also supports arm64 hosts). When it finishes you get the URL (`http://<container-ip>:8000`).

First sign-in details are in the container:

```bash
pct exec <CTID> -- cat /root/mvault.creds
```

Sign in as the administrator, change the generated password when asked, and **back up `MVAULT_ENCRYPTION_KEY` and `MVAULT_ENCRYPTION_SALT`** from `/etc/mvault/mvault.env` — without them stored values cannot be decrypted. See [Backup and restore](backup-restore.md).

Unattended installs honour the framework's `var_*` variables (for example `var_cpu`, `var_ram`, `var_disk`, `var_hostname`, `var_ctid`).

## Put a reverse proxy in front

The container serves plain HTTP on port 8000 and does not include a proxy. Terminate TLS with your own (Nginx Proxy Manager, Caddy, Traefik, …); see [Reverse proxy](reverse-proxy.md), then tell mVault its public address:

```bash
pct exec <CTID> -- mvault config set MVAULT_BASE_URL https://vault.example.com
pct exec <CTID> -- mvault restart
```

## Manage

Inside the container (`pct enter <CTID>`):

| Command | What it does |
|---|---|
| `mvault status` | Shows PostgreSQL, MinIO and the web app and the URL |
| `mvault restart` / `stop` / `start` | Controls the systemd services |
| `mvault logs [web\|minio]` | Follows the logs |
| `mvault backup` | Backs up the database and configuration to one `tar.gz` |
| `mvault doctor` | Checks the configuration |

## Update

From the Proxmox host, re-run the same one-liner inside the existing container, or directly in the container:

```bash
pct exec <CTID> -- mvault upgrade --yes
```

An update takes a backup first and rolls back if the new version does not start.

## Use your own PostgreSQL or S3 storage

Run the [native installer](native-install.md) flags inside the container instead (`--no-postgres --database-url …`, `--no-minio --s3-endpoint …`).

## Testing

What was verified: both scripts pass `shellcheck` and `bash -n`, and the installer they call is tested separately (see [native install](native-install.md)). **Not yet verified on a real Proxmox host:** container creation through the framework, systemd sandboxing inside an *unprivileged* LXC (the framework enables `nesting`, which the unit hardening needs), and the update path. If you try it, please report results in an issue.

## Submitting to community-scripts

Their contribution guide requires new scripts to be sent to their development repository first, tested on a real Proxmox instance, and reviewed; acceptance is not guaranteed and may depend on project adoption. The plan is to submit only after a real Proxmox test and once v0.4.0 has some real users; until then this page's one-liner is the supported route. The metadata sheet for that submission is in [`proxmox/SUBMISSION.md`](../proxmox/SUBMISSION.md).
