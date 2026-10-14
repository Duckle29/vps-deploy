# Uptime Kuma monitor setup

Monitor config lives only in the Kuma UIs (SQLite), so this file is the record and
the checklist. Tick a box when the monitor exists and shows green.

Last updated: 2026-10-13. Progress is as reported by Mikkel: home Kuma, group
"Public services" done, working on "Infrastructure". The external Kuma and
everything after Infrastructure are not ticked yet; tick what already exists.

## Split of responsibility

- **Home Kuma** (`status2.mikkel.cc`, VM 101): "is my stuff healthy on the LAN?".
  Tests the Caddy sites over the LAN (`etc_hosts` -> `host-gateway` in the play),
  and keeps working when the internet is down.
- **External Kuma** (`watch.mikkel.cc`, netcup): "can the world
  reach me?" and the dead-man switch for home itself.
- They watch each other. One monitor per failure mode on the external one, so a home
  outage is one alert, not fifteen.

## Global settings (both)

- [ ] Admin 2FA enabled: home
- [ ] Admin 2FA enabled: external
- [ ] Notification: Migadu SMTP, default-on: home
- [ ] Notification: Migadu SMTP, default-on: external
- [ ] Second, independent channel (ntfy / Telegram / Pushover), default-on: home
- [ ] Second, independent channel, default-on: external
- [ ] Retries 2-3, retry interval 20-60 s on every monitor
- [ ] Resend while down: every 60 checks (about hourly)
- [ ] Cert expiry notifications (14/7/3 days) on HTTPS monitors
- [ ] Monitor history retention 90 days
- [ ] Maintenance windows used for PVE reboots/upgrades

## Home Kuma (status2.mikkel.cc)

Public hostnames are the ones in `kuma_local_hosts` in `deploy_homeserver.yml`.
Add a name there if a new site gets a monitor.

### Group: Public services (LAN path via Caddy)

HTTPS, interval 60 s, timeout 20 s, retries 2, "ignore TLS errors" off.

- [x] mikkel.cc
- [x] blog.mikkel.cc
- [x] wifir.mikkel.cc
- [x] webhooks.mikkel.cc (accept 404)
- [x] paste.mikkel.cc
- [x] sche.cc (accept 302)
- [x] snuletek.org
- [x] lounge.mikkel.cc
- [x] lounge.snuletek.org: no separate monitor, same Caddy site as lounge.mikkel.cc
      (the second name exists because mikkel.cc is blocked at work)
- [x] nextcloud.mikkel.cc (`/status.php`, keyword `"installed":true`)
- [x] immich.mikkel.cc (`/api/server/ping`, keyword `pong`)
- [x] unifi.mikkel.cc / ubnt.mikkel.cc
- [x] joplin.mikkel.cc: not monitored on purpose; Joplin is being retired for Nextcloud Notes

### Group: Infrastructure (checked against /metrics 2026-10-14)

- [x] Proxmox UI `https://192.168.6.2:8006` (ignore TLS, keyword `Proxmox`)
- [x] PBS UI `https://192.168.6.205:8007` (ignore TLS)
- [x] NAS web UI `192.168.6.220:443` (TCP or HTTPS, ignore TLS)
- [x] NAS NFS TCP `192.168.6.220:2049` (VM 101 depends on it)
- [x] NAS SMB TCP `192.168.6.220:445`
- [ ] NAS ping `192.168.6.220`
- [ ] VM 101 SSH TCP `192.168.6.203:22` (monitor "SSH Microservices" exists but points at 192.168.6.220, the NAS; retarget)
- [x] UniFi gateway ping `192.168.6.1`
- [x] WAN: ping `1.1.1.1`
- [x] WAN: DNS monitor `mikkel.cc` against `1.1.1.1`

Not monitored: **SSH on the NAS**. SSH is off on HexOS (a TCP check on
`192.168.6.220:22` fails by design). Do not enable it just for Kuma; see
`docs/codify.md` for when it would be needed.

### Group: Backups and health (phase 2, push monitors)

Fed by `host-health.timer` on proxmox0 (every 5 min, script
`files/proxmox/host-health`, tokens `credentials.kuma.heartbeat.{ups,zfs}`).
Create each as a Push monitor with heartbeat interval 600 s, retries 1.

- [x] UPS (`ups`): down unless `STATUS` is `ONLINE`
- [x] ZFS health (`zfs`): down on `zpool status -x` problems or a pool >= 85 % full
      (host pools only; `HDDs` is inside the HexOS VM and is not visible)

### Watching the external Kuma

- [ ] HTTPS `https://watch.mikkel.cc/` (keyword `Uptime Kuma`)

## External Kuma (watch.mikkel.cc)

### Reachability and public path

- [ ] Home reachable: TCP `home.mikkel.cc:443`, 60 s, retries 3
- [ ] Caddy + TLS: HTTPS `https://sche.cc/<known code>`, accept 302, cert expiry on
- [ ] Nextcloud: `/status.php`, keyword `"installed":true`
- [ ] Immich: `/api/server/ping`, keyword `pong`
- [ ] Webhook server: `webhooks.mikkel.cc/`, accept 404
- [ ] Blog / snuletek.org: HTTPS, keyword from the page title
- [ ] Home Kuma alive: `https://status2.mikkel.cc/`, keyword `Uptime Kuma`

DNS-only names (`paste`, `sche.cc`, `webhooks`, `wifir`, `esp`, `mqtt`) show the
real certificate, so cert expiry alerts are meaningful there. Cloudflare-proxied
names show Cloudflare's certificate.

### Push monitors (existing, tokens in `credentials.kuma.heartbeat.*`)

Interval 26 h, retries 0 (period + grace).

- [ ] `host_config`
- [ ] `pbs_vms`
- [ ] `borg_pbs`
- [ ] `borg_nas`

### After the esp / mqtt migration

- [ ] esp OTA: TCP `esp.mikkel.cc:443`
- [ ] MQTT TLS: TCP `mqtt.mikkel.cc:8883`, 60 s
- [ ] ESP chain check: push monitor fed by a timer on netcup that runs
      `openssl s_client -verify_return_error` against `esp.mikkel.cc` with ISRG Root
      X1 pinned (the chain must end there; the cross-signed Root YR expires Sep 2032)

## Skipped on purpose

- Docker container monitors: need the Docker socket in Kuma (root-equivalent).
  HTTP checks cover the same ground.
- One monitor per path: one keyword check per app is enough.

## Related

- `deploy_homeserver.yml`, play "Install Uptime Kuma (status2.mikkel.cc)"
- `docs/proxmox0.md`: hosts, UPS, NAS addresses
- `docs/codify.md`: SSH / `midclt` questions for the NAS
