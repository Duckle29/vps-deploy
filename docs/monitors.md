# Uptime Kuma monitor setup

Monitor config lives only in the Kuma UIs (SQLite), so this file is the record and
the checklist. Tick a box when the monitor exists and shows green.

Last updated: 2026-10-16. Ticked from both Kumas' `/metrics` (all existing monitors
were UP, TLS certs valid). `/metrics` does not expose retries, intervals, resend,
cert-expiry notification settings, retention or maintenance windows, so those global
items stay unticked until confirmed in the UI. The esp/mqtt items wait on the ESPHome
decision (those services stay on the VPS).

## Split of responsibility

- **Home Kuma** (`status2.mikkel.cc`, VM 101): "is my stuff healthy on the LAN?".
  Tests the Caddy sites over the LAN (`etc_hosts` -> `host-gateway` in the play),
  and keeps working when the internet is down.
- **External Kuma** (`watch.mikkel.cc`, netcup): "can the world
  reach me?" and the dead-man switch for home itself.
- They watch each other. One monitor per failure mode on the external one, so a home
  outage is one alert, not fifteen.

## Global settings (both)

- [x] Admin 2FA enabled: home
- [x] Admin 2FA enabled: external
- [x] Notification: Migadu SMTP, default-on: home
- [x] Notification: Migadu SMTP, default-on: external
- [x] Second, independent channel (Discord), default-on: home
- [x] Second, independent channel (Discord), default-on: external
- [ ] Retries 2-3, retry interval 20-60 s on every monitor
- [ ] "Resend Notification if Down X times consecutively": 60 (about hourly), optional; 0 = one alert per outage
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
- [x] VM 101 SSH TCP `192.168.6.203:22` (monitor "SSH Microservices"; its stale URL field shows 192.168.6.220 in /metrics, the real hostname:port is correct)
- [x] UniFi gateway ping `192.168.6.1`
- [x] WAN: ping `1.1.1.1`
- [x] WAN: DNS monitor `mikkel.cc` against `1.1.1.1`

Not monitored: **SSH on the NAS**. SSH is off on HexOS (a TCP check on
`192.168.6.220:22` fails by design). Do not enable it just for Kuma; see
`docs/codify.md` for when it would be needed.

### Watching the external Kuma

- [x] HTTPS `https://watch.mikkel.cc/` (keyword `Uptime Kuma`)

## External Kuma (watch.mikkel.cc)

### Reachability and public path

- [x] Home reachable: TCP `home.mikkel.cc:443`, 60 s, retries 3
- [x] Caddy + TLS: HTTPS `https://sche.cc/<known code>`, accept 302, cert expiry on
- [x] Nextcloud: `/status.php`, keyword `"installed":true`
- [x] Immich: `/api/server/ping`, keyword `pong`
- [x] Webhook server: `webhooks.mikkel.cc/`, accept 404
- [x] Blog / snuletek.org: HTTPS, keyword from the page title
- [x] Home Kuma alive: `https://status2.mikkel.cc/`, keyword `Uptime Kuma`

DNS-only names (`paste`, `sche.cc`, `webhooks`, `wifir`, `esp`, `mqtt`) show the
real certificate, so cert expiry alerts are meaningful there. Cloudflare-proxied
names show Cloudflare's certificate.

### Push monitors (existing, tokens in `credentials.kuma.heartbeat.*`)

Interval 26 h, retries 0 (period + grace).

- [x] `host_config`
- [x] `pbs_vms`
- [x] `borg_pbs`
- [x] `borg_nas`

### Host health push monitors (live)

Fed by `host-health.timer` on proxmox0 (every 5 min, script
`files/proxmox/host-health`, tokens `credentials.kuma.heartbeat.{ups,zfs}`).
Push monitors, heartbeat interval 600 s, retries 1. They are on the external Kuma
on purpose: the home Kuma runs on the same host and UPS, so it cannot report that
host or the power going away; a missing heartbeat here is the alarm.

- [x] UPS (`ups`): down unless `STATUS` is `ONLINE`, or if `SELFTEST` is NG/BT.
      apcupsd's `onbattery`/`offbattery` hooks trigger an immediate push; ONBATT is
      re-read after 40 s so the ~20 s biweekly self test never notifies.
- [x] ZFS health (`zfs`): down on `zpool status -x` problems or a pool >= 85 % full
      (host pools only; `HDDs` is inside the HexOS VM and is not visible)

### ESP certificate bundle (play `espcerts`, deployed)

- [ ] Push monitor `espcerts` on the external Kuma (token in
      `credentials.kuma.heartbeat.espcerts`), heartbeat interval 8 days (the build
      runs weekly via `espcerts-bundle.timer`), retries 0. A failed build pushes
      down with the reason; a dead timer misses the heartbeat.
- [x] TCP `espcerts.mikkel.cc:8443` on the external Kuma (cert renewal is done by
      Caddy, an expired or missing cert shows as an HTTPS failure)

### esp OTA and MQTT (deployed 2026-10-17, DNS on the homeserver)

- [ ] esp OTA: TCP `esp.mikkel.cc:8445` (nginx, 512 B records; 8444 belongs to UniFi OS)
- [ ] MQTT TLS: TCP `mqtt.mikkel.cc:8883`, 60 s
- [ ] ESP chain check: push monitor fed by a timer on netcup that runs
      `openssl s_client -verify_return_error` against `esp.mikkel.cc:8445` with ISRG
      Root X1 pinned (the chain must end there; the cross-signed Root YR expires Sep
      2032). `mqtt.mikkel.cc:8883` serves the shorter ISRG Root X2 chain (leaf, YE1,
      Root YE), which the bundle also trusts: check it against X2 instead.

## Skipped on purpose

- Docker container monitors: need the Docker socket in Kuma (root-equivalent).
  HTTP checks cover the same ground.
- One monitor per path: one keyword check per app is enough.

## Related

- `deploy_homeserver.yml`, play "Install Uptime Kuma (status2.mikkel.cc)"
- `docs/proxmox0.md`: hosts, UPS, NAS addresses
- `docs/codify.md`: SSH / `midclt` questions for the NAS
