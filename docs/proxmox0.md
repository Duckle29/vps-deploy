# proxmox0: hand-made setup and host notes

Record of everything on the Proxmox host (`proxmox0`, 192.168.6.2, PVE node name
`home`), the NAS VM and the off-site storage that is **not** managed by
`proxmox.yml`. Whatever the playbook manages is listed in its header; this file is
the record of the rest. When something undocumented turns up, add it here.

Last reviewed: 2026-10-13, after the PVE 8 -> 9 upgrade.

## Host

### Platform and upgrades

- PVE 9.2.21 on Debian 13 trixie, kernel 7.0.14-23-pve. Upgraded from 8.4.21 on
  2026-10-13: about 5 minutes of dist-upgrade, run in tmux with `--force-confold`,
  so every config file is the pre-upgrade one (see "Config files" below).
- The node is called `home` (`pvesh /nodes/home/...`), not `proxmox0`, which is
  only the DNS name.
- The PVE install, the `rpool` ZFS mirror on the two NVMe drives, host network
  (vmbr0) and packages (borgbackup, nfs-common, tmux, apcupsd, amd64-microcode) are
  by hand. A rebuilt host needs these before `proxmox.yml` can be applied.
- tmux is installed. Long jobs: tmux with `pipe-pane` to a log file, or
  `systemd-run`.
- chrony 4.8 only started working after the post-upgrade reboot (it failed with
  "Could not send notification to $NOTIFY_SOCKET" while the old systemd was PID 1).
- Rollback point: ZFS snapshot `rpool@pre-pve9-upgrade` (recursive, 2026-10-13).
  Destroy it after a clean backup cycle. The PVE 8.4 one, `pre-pve84-upgrade`, was
  destroyed 2026-10-13.

### Network

- `vmbr0` bridges `enp11s0` (192.168.6.2/24, gw 192.168.6.1, VLAN aware).
- NIC pin: `/etc/systemd/network/10-enp11s0.link` (added 2026-10-13; matches MAC
  `d8:43:ae:c3:72:99`, `Name=enp11s0`; also baked into the initramfs) so a new
  kernel cannot rename the NIC that vmbr0 bridges.
- CT 105 network: `net0 hwaddr=BC:24:11:BF:FC:3D`, ip 192.168.6.205/24, gw
  192.168.6.1 (static inside the CT; the play's create step pins the same). UniFi
  has a static DHCP lease for that MAC -> 192.168.6.205, so a rebuilt CT must keep
  the hwaddr or the lease must be updated in UniFi.

### apt sources

All deb822 in `/etc/apt/sources.list.d`:

- `debian.sources`: ftp.dk.debian.org `trixie`, `trixie-updates` and
  `debian-security`, components main contrib non-free-firmware.
- `proxmox.sources`: `pve-no-subscription`, trixie.
- `pve-enterprise.sources`: created by the PVE 9 packages, and it makes every
  `apt update` fail with 401 (no subscription), so `Enabled: false` is appended.
  Check that line again after PVE upgrades.

Removed in the upgrade: `ceph.list` (ceph-quincy, unused), the misnamed
`pve-enterprise.list` (it held the PVE 8 no-subscription line) and the
`systemd-boot` meta-package (the wiki says to drop it unless systemd-boot was set
up by hand; the host boots grub through `proxmox-boot-tool`; `systemd-boot-efi`
stays). The old sources are copied in `/root/apt-backup-pve9`.

### Config files kept at the pre-upgrade version

Checked 2026-10-13, the `.dpkg-dist` leftovers were deleted:

- `/etc/lvm/lvm.conf`: ours is the stock file plus PVE's `global_filter` for
  `zd*`/`rbd*`, which must stay.
- `/etc/issue`: PVE regenerates the banner.
- `/etc/vzdump.conf` (our hook line, managed by the play) and
  `/etc/apcupsd/apcupsd.conf` (see UPS): keep ours at a conffile prompt.

### ZFS

- Only `rpool` belongs to the host.
- `/etc/zfs/zpool.cache` is written (`zpool set cachefile=/etc/zfs/zpool.cache
  rpool`) and `zfs-import-scan` is **masked**. Without the cache file the scan unit
  runs, finds the passthrough pool `HDDs` (the NAS data, owned by VM 103) and would
  import it on the host. ZFS refused it after the upgrade (other hostid), but a
  cleanly exported pool would have gone through. Never import `HDDs` on the host.

### UPS

- APC Back-UPS BX500MI ("lilSpark") on USB, apcupsd 3.14 on proxmox0.
- Stock `/etc/apcupsd/apcupsd.conf` with `UPSCABLE usb`, `UPSTYPE usb`,
  `BATTERYLEVEL 5`, `MINUTES 3`: the host shuts down at 5 % or 3 minutes left. About
  26 minutes of runtime at 15 % load.
- `NETSERVER on` at 127.0.0.1 only; no other host sees the UPS.
- The guests are stopped by the normal host shutdown (startup order, `up=120` for
  HexOS).

### Guests and storage

- VM 101's system disk (scsi0) is 200 GB, managed by `guest_disks` in `proxmox.yml`
  (grow only). It was grown from 100 GB on 2026-10-17; the partition and ext4
  inside the guest were grown by hand (`growpart /dev/sda 2`, `resize2fs /dev/sda2`).
  The disk has no `discard=on`, so space freed inside the guest is not returned to ZFS.

- Existing VM 101 and 103 are only touched for `guest_settings` and `guest_disks`.
  `proxmox.yml` play 3 (tag `vms`) can CREATE either one when it is missing; it
  has never replaced a live VM. The HexOS install itself (GUI), the TrueNAS
  config and the data on VM 101 (restore from PBS) are not covered. The `local`
  storage gets the `snippets` content type when VM 101 is created., and CT 105's cores/memory/rootfs/net0 after creation (the
  create step uses the values in the play).
- `storage.cfg`: `local`, `local-zfs`, and `hexos-share` (CIFS, empty, obsolete;
  remove with `pvesm remove`).

### Secrets on the host

- `/root/.config/borg/*.pass` and `/root/.ssh/borg_*_ed25519`: the Storage Box
  sub-account keys, restricted to append-only on the Hetzner side.
- The pbs-main token lives in `/etc/pve/priv/storage/` (written by the play) and
  the PBS web UI admin password in `/root/pbs-admin.pw` inside CT 105.

## HexOS VM 103 (the NAS, TrueNAS-based, 192.168.6.220)

- q35 + OVMF, 8 cores, 10 GiB, 64 GiB system disk on local-zfs (scsi0).
- Three 4 TB Seagate IronWolf drives (ST4000VN006, serials WW6567VB, WW6566MD,
  WW6566YR) are passed through as raw `/dev/disk/by-id` block devices (scsi1-3,
  `backup=0` so vzdump skips them), **not** PCI passthrough. They hold the pool
  `HDDs`; the system disk is the only part of 103 that PBS backs up.
- The NAS data is protected only by the off-site borg job; the VM backup does not
  contain it.
- HexOS itself was installed from the ISO by hand and configured in its UI (pool
  HDDs, users, SMB/NFS shares). That config is not in git; a TrueNAS config export
  (System > General) is still to be saved.

## TrueNAS (HexOS UI): what makes the off-site job work

### Cron job "snapshot-clone"

Root, daily 03:15, output hidden. It clones the newest snapshot of each dataset
read-only to `HDDs/offsite-clones/<ds>`, which is what the borg job reads over NFS
(TrueNAS has no crossmnt, so snapshots show up empty over NFS). nfsd keeps an
exported dataset busy, so the clone has to be unexported before the destroy and
re-exported at the end. The command, one line in the UI (line breaks here are for
reading):

```sh
sh -c 'rc=0; for ds in microservices mikkel haosBackups; do
  snap=$(zfs list -H -t snapshot -o name -s creation "HDDs/$ds" | grep "^HDDs/$ds@" | tail -1);
  [ -n "$snap" ] || { echo "no snapshot for HDDs/$ds" >&2; rc=1; continue; };
  exportfs -u "192.168.6.2:/mnt/HDDs/offsite-clones/$ds" 2>/dev/null; exportfs -f;
  zfs destroy -f "HDDs/offsite-clones/$ds" || rc=1;
  zfs clone -o readonly=on "$snap" "HDDs/offsite-clones/$ds" || rc=1;
done; exportfs -ra; exit $rc'
```

### NFS shares

- For 192.168.6.2, read-only, maproot root: one per clone,
  `/mnt/HDDs/offsite-clones/{microservices,mikkel,haosBackups}`.
- rw share "Bulk storage for microservices server" (`/mnt/HDDs/microservices`,
  192.168.6.203): VM 101's data. Must stay.
- The old read-only shares `offsite-ro-{microservices,mikkel,haosbackups}` (host
  192.168.6.2) are obsolete and can be deleted once the nightly run is verified.

### Snapshot tasks (Data Protection)

- One per dataset `HDDs/{microservices,mikkel,haosBackups,HAOS}`, not recursive,
  daily at 00:00, naming schema `auto-%Y-%m-%d_%H-%M`, retention 1 week.
- So the off-site copy is the NAS as of midnight: snapshot 00:00, clone 03:15,
  borg 03:30.
- `HDDs/HAOS` is empty (meant for 3D print videos, never set up) and deliberately
  has no clone or borg job; add it to `nas_clone_datasets` and the cron if it
  fills.
- A clone pins its origin snapshot, so the one in use cannot be pruned by the
  expiry while it is cloned; the cron re-clones nightly.

### Old rsync task

The old rsync task (`/mnt/HDDs` -> BorgPi, daily 00:00) is obsolete and must stay
disabled or deleted: it recursed into the clones, kept them busy and pushed them to
the Pi as if they were new data.

## Hetzner Storage Box

BX21, port 23, `--remote-path=borg-1.4`. Account and host are in
`vars/credentials.yml` (`borg.storage_box`).

- Sub-account 1 -> `./nas-data` (borg-nas-offsite), sub-account 2 ->
  `./pbs-datastore` (borg-pbs-offsite). Each has an append-only restricted key.
- The sub-account passwords must differ from the borg passphrases: a password login
  bypasses append-only.
- Admin access is the desktop key.

## Related

- `docs/codify.md`: which of the above could be moved into Ansible, and in what
  order.
- `proxmox.yml`: what the playbook manages (PBS container, backup scripts, units,
  Kuma env files, vzdump job, NFS automounts, guest settings).
- `files/proxmox/`: the scripts the playbook installs. Never run `pbs-setup.sh` on
  the live CT without `-e pbs_force_setup=true`: it rotates the pvesm token.
