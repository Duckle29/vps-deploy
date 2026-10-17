# VPS (contabo1) wind-down

State on 2026-10-17: everything that served traffic has moved to the homeserver
(bepasty, shlink, snuletek, webhook + static sites, esp OTA on :8445, Mosquitto on
:8883, ciao -> Kuma). DNS for those names points at `home.mikkel.cc`; the user
stopped all containers on the VPS on 2026-10-17. What is left is deciding what to
keep, archiving it and cancelling the contract.

Read-only survey done without root, so database contents were not inspected.

## To decide

- [ ] **bw.mikkel.cc**: `bitwarden_rs` container (image from 2021, was "unhealthy"),
      data in volume `bitwarden_rs` (`db.sqlite3`, rsa keys). Still the password
      manager? If not, export the vault once before shutdown. DNS still on the VPS.
- [ ] **DNS records still pointing at the VPS**, delete or keep each: `autotorrent`,
      `bw`, `cocalc`, `git`, `ofsm`, `unms`, `unms2` (all `.mikkel.cc`). Their
      containers (gitea, cocalc, factorio, unms) have been stopped for months.
- [ ] **Host services**, still active: `deluged` (autotorrent, port 58846), `mariadb`
      (3306), `mongodb`, `php7.4-fpm`, `nginx`. Check what each holds before it goes.
- [ ] **VPN**: listeners on 10.100.100.2 / 10.100.101.1 port 55916 and volume
      `ovpn-data-contabo`, plus `CLIENTNAME.ovpn` / `streampi1.ovpn` in the home
      directory. Does anything still connect through it?
- [ ] **Old nginx site `esp.conf`, `ciao2.conf`, `cvat.conf`** (root-only, not read).

## To archive (needs root; disk is 95 % full, 353 GB used)

- [ ] `/home/mikkel` (21 GB; includes `nextcloud-db-dmp`, `duckle_sqlite.tar.gz`,
      game saves, `projects`, `qmk_firmware`, ...), skim before copying
- [ ] Docker volumes with real data: `nextcloud_data`, `nc_db`, `nextcloud_db`,
      `nc_webroot`, `gitea_data`, `gitea_db`, `bitwarden_rs`, `shlink_db`,
      `bepasty_data` (incl. the expired pastes), `ciao_data`, `thelounge_data`,
      `sopel_data`, `cocalc_data`, `pk_data`, `pk_mariadb`, `cvat_*`, UNMS volumes
- [ ] MariaDB and MongoDB dumps from the host services (root / password needed)
- [ ] Anything else under `/srv`, `/etc/nginx`, `/etc/letsencrypt`-style cert dirs
      worth keeping for reference

## Then

- [ ] Delete the stale DNS records (and `contabo1` itself last)
- [x] Removed `deploy.yml` (all plays were `[vps]`) and `templates/nginx/sites/` on 2026-10-17
- [ ] Cancel the contract

## Decisions (2026-10-17)

Nothing from the VPS is archived. Dropped on purpose: `bitwarden_rs`, `bepasty_data`,
`/home/mikkel`, the Nextcloud volumes, the MariaDB/MongoDB dumps, `pk_*`, the VPN
(`ovpn-data-contabo`, `.ovpn` files), `/etc/nginx`, `ciao_data`, `thelounge_data`,
`sopel_data`, UNMS, `cvat_cvat_*`, `cocalc_data`, `gitea_*`, `esp-ota_data`,
`esp_update_server`, `satisfactory_data`, `mc_pomodoro_data`, the `duQTT*` broker
volumes and the anonymous volumes.

- [x] Stale DNS records deleted (checked 2026-10-17: autotorrent, bw, cocalc, git,
      ofsm, unms and unms2 no longer resolve)
