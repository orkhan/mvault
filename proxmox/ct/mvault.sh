#!/usr/bin/env bash
_cs_boot="${COMMUNITY_SCRIPTS_CORE_DIR:-$(dirname "${BASH_SOURCE[0]}")/../../core}/core/build.func"
source "$_cs_boot" 2>/dev/null || source <(curl -fsSL "${COMMUNITY_SCRIPTS_CORE_URL:-https://raw.githubusercontent.com/community-scripts/core/main}/core/build.func")
# Copyright (c) 2026 Orkhan Maharramli
# License: MIT | https://github.com/orkhan/mvault/blob/main/LICENSE
# Source: https://github.com/orkhan/mvault
#
# Run it straight from the mVault repository (before/without community-scripts):
#   COMMUNITY_SCRIPTS_URL=https://raw.githubusercontent.com/orkhan/mvault/main/proxmox \
#     bash -c "$(curl -fsSL https://raw.githubusercontent.com/orkhan/mvault/main/proxmox/ct/mvault.sh)"

APP="mVault"
var_tags="${var_tags:-password-manager;vault}"
var_cpu="${var_cpu:-2}"
var_ram="${var_ram:-2048}"
var_disk="${var_disk:-8}"
var_os="${var_os:-debian}"
var_version="${var_version:-13}"
var_arm64="${var_arm64:-yes}"
var_unprivileged="${var_unprivileged:-1}"

# Optional install-time settings, all read by install/mvault-install.sh. Leave them unset for the default
# (PostgreSQL and MinIO installed inside the container). They can be preset for unattended installs:
#   var_database_url      postgres://user:password@host:5432/dbname  -> use this PostgreSQL, install none      (secret)
#   var_s3_endpoint       https://s3.example.lan:9000                -> use this S3 storage, install no MinIO
#   var_s3_access_key     S3 access key                                                                       (secret)
#   var_s3_secret_key     S3 secret key                                                                       (secret)
#   var_provision_buckets yes                                        -> create the buckets if missing (needs CreateBucket)
#   var_no_storage        yes                                        -> run without object storage (no icons/avatars/files)
#   var_base_url          https://vault.example.com                  -> public URL (default http://<container-ip>:8000)
#   var_admin_email       you@example.com                            -> first administrator (default admin@mvault.local)
export var_database_url="${var_database_url:-}"
export var_s3_endpoint="${var_s3_endpoint:-}"
export var_s3_access_key="${var_s3_access_key:-}"
export var_s3_secret_key="${var_s3_secret_key:-}"
export var_provision_buckets="${var_provision_buckets:-}"
export var_no_storage="${var_no_storage:-}"
export var_base_url="${var_base_url:-}"
export var_admin_email="${var_admin_email:-}"

header_info "$APP"
variables
color
catch_errors

# Interactive installs only: offer to use an existing PostgreSQL / S3 instead of installing them in the container.
function ask_external_services() {
  [[ -t 0 && -t 1 ]] || return 0
  [[ -n "$var_database_url$var_s3_endpoint$var_no_storage" ]] && return 0
  command -v whiptail >/dev/null 2>&1 || return 0

  if whiptail --backtitle "mVault" --title "PostgreSQL" --defaultno --yesno \
    "Use an EXISTING PostgreSQL server instead of installing one in the container?" 9 62; then
    var_database_url="$(whiptail --backtitle "mVault" --title "PostgreSQL URL" --inputbox \
      "postgres://user:password@host:5432/dbname" 9 70 "" 3>&1 1>&2 2>&3)" || var_database_url=""
    export var_database_url
  fi
  if whiptail --backtitle "mVault" --title "Object storage" --defaultno --yesno \
    "Use an EXISTING S3-compatible storage (MinIO, Ceph, ...) instead of installing MinIO in the container?\n\nChoose No to install MinIO." 11 66; then
    var_s3_endpoint="$(whiptail --backtitle "mVault" --title "S3 endpoint" --inputbox \
      "Endpoint URL, e.g. http://minio.lan:9000 (leave empty to run WITHOUT object storage)" 10 70 "" 3>&1 1>&2 2>&3)" || var_s3_endpoint=""
    if [[ -n "$var_s3_endpoint" ]]; then
      var_s3_access_key="$(whiptail --backtitle "mVault" --title "S3 access key" --inputbox "Access key" 9 60 "" 3>&1 1>&2 2>&3)" || var_s3_access_key=""
      var_s3_secret_key="$(whiptail --backtitle "mVault" --title "S3 secret key" --passwordbox "Secret key" 9 60 "" 3>&1 1>&2 2>&3)" || var_s3_secret_key=""
    else
      var_no_storage="yes"
    fi
    export var_s3_endpoint var_s3_access_key var_s3_secret_key var_no_storage
  fi
}

function update_script() {
  header_info
  check_container_storage
  check_container_resources

  if [[ ! -x /usr/local/bin/mvault || ! -d /opt/mvault ]]; then
    msg_error "No ${APP} Installation Found!"
    exit
  fi

  if check_for_gh_release "mvault" "orkhan/mvault"; then
    msg_info "Updating ${APP} to ${CHECK_UPDATE_RELEASE} (a backup is taken first)"
    $STD mvault upgrade --yes --version "${CHECK_UPDATE_RELEASE#v}"
    echo "${CHECK_UPDATE_RELEASE#v}" >~/.mvault
    msg_ok "Updated ${APP}"
  fi
  exit
}

start
ask_external_services
build_container
description

msg_ok "Completed successfully!\n"
echo -e "${CREATING}${GN}${APP} setup has been successfully initialized!${CL}"
echo -e "${INFO}${YW}Access it using the following URL (put a TLS reverse proxy in front for production):${CL}"
echo -e "${TAB}${GATEWAY}${BGN}http://${IP}:8000${CL}"
echo -e "${INFO}${YW}First sign-in credentials are in the container:${CL} ${BGN}cat ~/mvault.creds${CL}"
