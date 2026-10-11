#!/usr/bin/env bash
# Tests the var_* -> installer flag mapping of install/mvault-install.sh without Proxmox or the framework.
#   bash proxmox/test/args-test.sh
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1090
source <(sed -n '/^# BEGIN build_installer_args/,/^# END build_installer_args/p' install/mvault-install.sh)
LOCAL_IP=10.0.0.5
fail=0
run() { # run <name> <expected flags, space separated | ERROR> -- VAR=value...
  local name="$1" expected="$2"; shift 3
  local out rc
  out="$(env -i LOCAL_IP="$LOCAL_IP" "$@" bash -c "$(declare -f build_installer_args); build_installer_args" 2>/dev/null | tr '\n' ' ')"; rc=${PIPESTATUS[0]}
  out="${out% }"
  if [[ "$expected" == ERROR ]]; then
    env -i LOCAL_IP="$LOCAL_IP" "$@" bash -c "$(declare -f build_installer_args); build_installer_args" >/dev/null 2>&1 && { echo "FAIL $name: expected an error"; fail=1; return; }
  elif [[ "$out" != "$expected" ]]; then echo "FAIL $name"; echo "  want: $expected"; echo "  got:  $out"; fail=1; return; fi
  echo "ok   $name"
}
run defaults            "--yes --base-url http://10.0.0.5:8000" --
run base-and-admin      "--yes --base-url https://v.example.com --admin-email a@b.c" -- var_base_url=https://v.example.com var_admin_email=a@b.c
run external-db         "--yes --base-url http://10.0.0.5:8000 --no-postgres --database-url postgres://u:p@h:5432/d" -- var_database_url=postgres://u:p@h:5432/d
run bad-db-url          ERROR -- var_database_url=mysql://x
run external-s3         "--yes --base-url http://10.0.0.5:8000 --no-minio --s3-endpoint http://m:9000 --s3-access-key AK --s3-secret-key SK" -- var_s3_endpoint=http://m:9000 var_s3_access_key=AK var_s3_secret_key=SK
run external-s3-buckets "--yes --base-url http://10.0.0.5:8000 --no-minio --s3-endpoint https://m --s3-access-key AK --s3-secret-key SK --provision-buckets" -- var_s3_endpoint=https://m var_s3_access_key=AK var_s3_secret_key=SK var_provision_buckets=yes
run s3-missing-keys     ERROR -- var_s3_endpoint=http://m:9000
run s3-bad-endpoint     ERROR -- var_s3_endpoint=minio:9000 var_s3_access_key=a var_s3_secret_key=b
run no-storage          "--yes --base-url http://10.0.0.5:8000 --no-minio --no-storage" -- var_no_storage=yes
run db-and-s3           "--yes --base-url http://10.0.0.5:8000 --no-postgres --database-url postgresql://u:p@h/d --no-minio --s3-endpoint http://m --s3-access-key a --s3-secret-key b" -- var_database_url=postgresql://u:p@h/d var_s3_endpoint=http://m var_s3_access_key=a var_s3_secret_key=b
exit $fail
