# Proxmox VE LXC

> **Coming in v0.4.0.** This page is a skeleton that records the design from [PLAN.md](../PLAN.md) (Phase 5). The script is being written by another workstream and is **not yet available**; details will be finalised after it has been tested on a real Proxmox host.

## Plan

A [community-scripts](https://community-scripts.org/)-style helper (`ct/mvault.sh` + `install/mvault-install.sh`) that creates an unprivileged Debian LXC and installs mVault **natively, without Docker**: PostgreSQL from apt, a Python virtual environment in `/opt/mvault`, the pinned-source MinIO binary, systemd services and the `mvault` CLI — the same layout as the Linux [native install](native-install.md). Suggested defaults: 2 vCPU, 2 GB RAM, 8 GB disk. Credentials are written to `/root/mvault.creds`; updating the container re-runs the upgrade steps.

Unattended installs will honour `var_*` variables, with options to use an existing PostgreSQL or S3 endpoint.

## Status

- Submission to community-scripts is **not** made yet. Their guide requires new scripts to go to their development repository first, be tested on a real Proxmox instance, and pass review; acceptance is not guaranteed.
- Until it is accepted, a one-liner in this repository will create the LXC with `pct` and run the native installer inside it.

## Until then

Create a Debian LXC yourself and use the [Docker](installation.md) path inside a VM, or [build from source](development.md).
