#!/usr/bin/env bash

# Copyright (c) 2026 Orkhan Maharramli
# License: MIT | https://github.com/orkhan/mvault/blob/main/LICENSE
# Source: https://github.com/orkhan/mvault

source /dev/stdin <<<"$FUNCTIONS_FILE_PATH"
color
verb_ip6
catch_errors
setting_up_container
network_check
update_os

msg_info "Installing Dependencies"
$STD apt install -y curl ca-certificates
msg_ok "Installed Dependencies"

# mVault's own installer is the single Linux install path (also used outside Proxmox): it installs
# PostgreSQL from apt, a uv-managed Python venv, the MinIO binary, systemd units and the `mvault` CLI.
msg_info "Installing mVault with PostgreSQL and MinIO"
INSTALL_SH="$(mktemp)"
INSTALL_LOG="$(mktemp)"
curl -fsSL "https://github.com/orkhan/mvault/releases/latest/download/install.sh" -o "$INSTALL_SH"
if ! sh "$INSTALL_SH" --yes --base-url "http://${LOCAL_IP}:8000" >"$INSTALL_LOG" 2>&1; then
  cat "$INSTALL_LOG" >&2
  msg_error "mVault installation failed"
  exit 1
fi
msg_ok "Installed mVault"

msg_info "Saving first sign-in credentials"
ADMIN_EMAIL="$(sed -n 's/^ *Sign in: *\([^ ]*\).*/\1/p' "$INSTALL_LOG" | head -n1)"
ADMIN_PASSWORD="$(sed -n 's/^ *Password: *\([0-9a-f]*\).*/\1/p' "$INSTALL_LOG" | head -n1)"
{
  echo "mVault URL:            http://${LOCAL_IP}:8000"
  echo "mVault admin e-mail:   ${ADMIN_EMAIL:-admin@mvault.local}"
  echo "mVault admin password: ${ADMIN_PASSWORD:-<existing installation: unchanged>} (you must change it at first sign-in)"
  echo "Configuration/secrets: /etc/mvault/mvault.env  (BACK UP MVAULT_ENCRYPTION_KEY and MVAULT_ENCRYPTION_SALT)"
  echo "Manage:                mvault status | restart | logs | backup | upgrade | doctor"
} >~/mvault.creds
chmod 600 ~/mvault.creds
CURRENT_VERSION="$(mvault version 2>/dev/null | head -n1 | sed -E 's/[^0-9]*([0-9]+\.[0-9]+\.[0-9]+).*/\1/')"
echo "${CURRENT_VERSION}" >~/.mvault
rm -f "$INSTALL_SH" "$INSTALL_LOG"
msg_ok "Saved credentials to ~/mvault.creds"

motd_ssh
customize
cleanup_lxc
