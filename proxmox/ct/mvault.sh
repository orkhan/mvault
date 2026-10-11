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

header_info "$APP"
variables
color
catch_errors

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
build_container
description

msg_ok "Completed successfully!\n"
echo -e "${CREATING}${GN}${APP} setup has been successfully initialized!${CL}"
echo -e "${INFO}${YW}Access it using the following URL (put a TLS reverse proxy in front for production):${CL}"
echo -e "${TAB}${GATEWAY}${BGN}http://${IP}:8000${CL}"
echo -e "${INFO}${YW}First sign-in credentials are in the container:${CL} ${BGN}cat ~/mvault.creds${CL}"
