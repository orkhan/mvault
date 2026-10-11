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
# BEGIN build_installer_args (exercised by proxmox/test/args-test.sh)
# Turns the optional var_* settings into installer flags. Prints one flag per line; returns non-zero on bad input.
build_installer_args() {
  local base_url="${var_base_url:-http://${LOCAL_IP}:8000}"
  printf '%s\n' "--yes" "--base-url" "$base_url"
  [[ -n "${var_admin_email:-}" ]] && printf '%s\n' "--admin-email" "$var_admin_email"
  if [[ -n "${var_database_url:-}" ]]; then
    [[ "$var_database_url" =~ ^postgres(ql)?://[^[:space:]]+$ ]] || { echo "var_database_url must look like postgres://user:password@host:5432/dbname" >&2; return 1; }
    printf '%s\n' "--no-postgres" "--database-url" "$var_database_url"
  fi
  if [[ "${var_no_storage:-}" == "yes" ]]; then
    printf '%s\n' "--no-minio" "--no-storage"
  elif [[ -n "${var_s3_endpoint:-}" ]]; then
    [[ "$var_s3_endpoint" =~ ^https?://[^[:space:]]+$ ]] || { echo "var_s3_endpoint must start with http:// or https://" >&2; return 1; }
    [[ -n "${var_s3_access_key:-}" && -n "${var_s3_secret_key:-}" ]] || { echo "var_s3_access_key and var_s3_secret_key are required with var_s3_endpoint" >&2; return 1; }
    printf '%s\n' "--no-minio" "--s3-endpoint" "$var_s3_endpoint" "--s3-access-key" "$var_s3_access_key" "--s3-secret-key" "$var_s3_secret_key"
    [[ "${var_provision_buckets:-}" == "yes" ]] && printf '%s\n' "--provision-buckets"
  fi
  return 0
}
# END build_installer_args

# Capture first: mapfile would swallow the function's exit status when fed through process substitution.
if ! INSTALLER_ARGS_OUT="$(build_installer_args)"; then
  msg_error "Invalid mVault installation settings (see message above)"
  exit 1
fi
mapfile -t INSTALLER_ARGS <<<"$INSTALLER_ARGS_OUT"
[[ -n "${var_database_url:-}" ]] && USING_EXTERNAL_DB=1 || USING_EXTERNAL_DB=0
[[ -n "${var_s3_endpoint:-}${var_no_storage:-}" ]] && USING_EXTERNAL_S3=1 || USING_EXTERNAL_S3=0

msg_info "Installing mVault ($([[ $USING_EXTERNAL_DB == 1 ]] && echo "external PostgreSQL" || echo "PostgreSQL"), $([[ "${var_no_storage:-}" == "yes" ]] && echo "no object storage" || { [[ $USING_EXTERNAL_S3 == 1 ]] && echo "external S3" || echo "MinIO"; }))"
INSTALL_SH="$(mktemp)"
INSTALL_LOG="$(mktemp)"
curl -fsSL "https://github.com/orkhan/mvault/releases/latest/download/install.sh" -o "$INSTALL_SH"
if ! sh "$INSTALL_SH" "${INSTALLER_ARGS[@]}" >"$INSTALL_LOG" 2>&1; then
  cat "$INSTALL_LOG" >&2
  msg_error "mVault installation failed"
  exit 1
fi
msg_ok "Installed mVault"

msg_info "Saving first sign-in credentials"
ADMIN_EMAIL="$(sed -n 's/^ *Sign in: *\([^ ]*\).*/\1/p' "$INSTALL_LOG" | head -n1)"
ADMIN_PASSWORD="$(sed -n 's/^ *Password: *\([0-9a-f]*\).*/\1/p' "$INSTALL_LOG" | head -n1)"
{
  echo "mVault URL:            ${var_base_url:-http://${LOCAL_IP}:8000}"
  echo "mVault admin e-mail:   ${ADMIN_EMAIL:-admin@mvault.local}"
  echo "mVault admin password: ${ADMIN_PASSWORD:-<existing installation: unchanged>} (you must change it at first sign-in)"
  echo "Configuration/secrets: /etc/mvault/mvault.env  (BACK UP MVAULT_ENCRYPTION_KEY and MVAULT_ENCRYPTION_SALT)"
  [[ $USING_EXTERNAL_DB == 1 ]] && echo "PostgreSQL:            external (DATABASE_URL in mvault.env); backups of that database are your responsibility"
  [[ "${var_no_storage:-}" == "yes" ]] && echo "Object storage:        disabled (icons, avatars and file records are unavailable)"
  [[ $USING_EXTERNAL_S3 == 1 && "${var_no_storage:-}" != "yes" ]] && echo "Object storage:        external S3 at ${var_s3_endpoint} (create the buckets mvault-icons, mvault-avatars, mvault-attachments unless var_provision_buckets=yes)"
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
