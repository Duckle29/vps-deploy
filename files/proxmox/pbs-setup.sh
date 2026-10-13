#!/usr/bin/env bash
# Runs INSIDE the PBS container (CT 105, Debian 13 trixie, Proxmox Backup Server 4).
# Safe to re-run. Secrets (admin password, PVE API token) are written to
# root-only files in the container and never printed.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
umask 022   # apt keys/lists must be world-readable; secrets get umask 077 below

KEYRING=/usr/share/keyrings/proxmox-archive-keyring.gpg
KEYRING_SHA256=136673be77aba35dcce385b28737689ad64fd785a797e57897589aed08db6e45

drop_enterprise_repo() {
  # The PBS package installs an enterprise repo that needs a paid subscription
  # (401 Unauthorized). We use pbs-no-subscription instead.
  local f
  for f in /etc/apt/sources.list.d/*; do
    [ -e "$f" ] || continue
    if grep -qs "enterprise.proxmox.com/debian/pbs" "$f"; then rm -f "$f"; fi
  done
}

echo "== install Proxmox Backup Server 4"
drop_enterprise_repo
apt-get update -qq
apt-get install -y -qq wget ca-certificates jq openssl

if [ ! -s "$KEYRING" ] || ! echo "$KEYRING_SHA256  $KEYRING" | sha256sum -c --status; then
  # Once the proxmox-archive-keyring package is installed it may replace this
  # file with a different (but valid) one, so only fail if it is not installed.
  if ! dpkg -s proxmox-archive-keyring >/dev/null 2>&1; then
    wget -qO "$KEYRING" https://enterprise.proxmox.com/debian/proxmox-archive-keyring-trixie.gpg
    echo "$KEYRING_SHA256  $KEYRING" | sha256sum -c --status \
      || { echo "ERROR: keyring checksum mismatch" >&2; rm -f "$KEYRING"; exit 1; }
  fi
fi
chmod 0644 "$KEYRING"

cat > /etc/apt/sources.list.d/proxmox.sources <<EOF
Types: deb
URIs: http://download.proxmox.com/debian/pbs
Suites: trixie
Components: pbs-no-subscription
Signed-By: $KEYRING
EOF
chmod 0644 /etc/apt/sources.list.d/proxmox.sources
apt-get update -qq
apt-get install -y -qq proxmox-backup-server
drop_enterprise_repo   # the package (re)adds it; keep it out so later updates work

echo "== datastore"
mkdir -p /datastore/main
chown backup:backup /datastore/main
if ! proxmox-backup-manager datastore list --output-format json | jq -e '.[] | select(.name=="main")' >/dev/null; then
  # A rebuilt container finds the old chunk store on the bind mount: adopt it.
  reuse=()
  [ -d /datastore/main/.chunks ] && reuse=(--reuse-datastore true)
  proxmox-backup-manager datastore create main /datastore/main --gc-schedule 'sat 03:00' "${reuse[@]}"
fi

echo "== users (admin for the web UI, pve for Proxmox VE)"
umask 077
user_exists() { proxmox-backup-manager user list --output-format json | jq -e --arg u "$1" '.[] | select(.userid==$u)' >/dev/null; }

if ! user_exists admin@pbs; then
  pw="$(openssl rand -base64 24)"
  proxmox-backup-manager user create admin@pbs --password "$pw" --comment "web UI admin"
  printf '%s\n' "$pw" > /root/pbs-admin.pw
  unset pw
fi
proxmox-backup-manager acl update / Admin --auth-id admin@pbs

if ! user_exists pve@pbs; then
  proxmox-backup-manager user create pve@pbs --comment "Proxmox VE backups"
fi
if [ ! -s /root/pvesm.token ]; then
  # generate-token has no --output-format; it prints a JSON "Result: {...}" block
  # containing "value". Extract it without ever echoing the secret.
  rm -f /root/pvesm.token
  proxmox-backup-manager user delete-token pve@pbs pvesm >/dev/null 2>&1 || true
  token_out="$(proxmox-backup-manager user generate-token pve@pbs pvesm)"
  printf '%s' "$token_out" | grep -oP '"value"\s*:\s*"\K[^"]+' > /root/pvesm.token
  unset token_out
  if [ ! -s /root/pvesm.token ]; then
    rm -f /root/pvesm.token
    echo "ERROR: could not extract the API token" >&2
    exit 1
  fi
fi
proxmox-backup-manager acl update /datastore/main DatastoreBackup --auth-id pve@pbs
proxmox-backup-manager acl update /datastore/main DatastoreBackup --auth-id 'pve@pbs!pvesm'

echo "== prune and verify jobs"
if ! proxmox-backup-manager prune-job list --output-format json | jq -e '.[] | select(.id=="main-prune")' >/dev/null; then
  proxmox-backup-manager prune-job create main-prune --store main --schedule '03:00' \
    --keep-daily 7 --keep-weekly 4 --keep-monthly 6
fi
if ! proxmox-backup-manager verify-job list --output-format json | jq -e '.[] | select(.id=="main-verify")' >/dev/null; then
  proxmox-backup-manager verify-job create main-verify --store main --schedule 'sun 04:00' \
    --ignore-verified true --outdated-after 30
fi

echo "== summary (no secrets)"
proxmox-backup-manager versions | sed -n 1p
proxmox-backup-manager datastore list
proxmox-backup-manager prune-job list
proxmox-backup-manager verify-job list
echo "-- certificate fingerprint:"
proxmox-backup-manager cert info | grep -i fingerprint
echo "-- secrets stored (sizes only):"
ls -l /root/pbs-admin.pw /root/pvesm.token
echo "-- web UI: https://192.168.6.205:8007"
