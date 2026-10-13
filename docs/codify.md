# Codify: what of `docs/proxmox0.md` can move into Ansible

Assessment written 2026-10-13, after the PVE 8 -> 9 upgrade. Nothing here is done
yet. Every item is something recorded by hand in `docs/proxmox0.md`; when one is
codified, move it from there into `proxmox.yml` (and its MANAGED list in the header).

Honest framing: a rebuild stays untested whichever way this goes. The gain is
documentation and drift detection (`--check --diff` showing `changed=0`) more than
disaster recovery. The PBS backups of VM 101/103 and CT 105 are what actually
rebuild the guests.

## Easy: plain Ansible modules, idempotent, `--check` works

A third play, "Host baseline", about 100 lines. Roughly an afternoon, mostly
testing against `--check --diff` on the live host (should show `changed=0`).

| Item | How |
|---|---|
| Packages: borgbackup, nfs-common, tmux, apcupsd, amd64-microcode | `ansible.builtin.apt` |
| apt sources: `debian.sources`, `proxmox.sources`, `Enabled: false` in `pve-enterprise.sources` | `copy`/`template`, `lineinfile` for the enabled flag |
| NIC pin `/etc/systemd/network/10-enp11s0.link` | `copy` + handler `update-initramfs -u -k all` |
| ZFS import safety: `zpool set cachefile=/etc/zfs/zpool.cache rpool`, mask `zfs-import-scan` | `command` guarded by `zpool get`, `systemd` with `masked: true` |
| UPS: `apcupsd.conf` (about 8 values) and service | `template`, `systemd` |
| Remove the `hexos-share` CIFS storage | `pvesm remove`, guarded by `pvesm status` |

Do the ZFS cachefile + mask first: it has the worst failure mode (the host
importing the NAS pool `HDDs` that VM 103 owns).

## Medium

- **VM 101/103 and CT 105 definitions** (CPU, memory, NICs, the raw
  `/dev/disk/by-id` passthrough of VM 103). `qm set` or
  `community.general.proxmox_kvm`. PBS already backs up each guest's config, so the
  value is drift detection and documenting the passthrough disks. Use `--check`
  only and never overwrite a live VM, like the existing create-only pattern.
- **Secrets on the host** (`/root/.config/borg/*.pass`, `/root/.ssh/borg_*_ed25519`).
  Passphrases can come from `credentials.yml` (already kept out of the repo). The
  Storage Box side (restricted `authorized_keys` per sub-account) stays manual.
  Private keys are either generated once and vaulted, or regenerated and
  re-authorized by hand.
- **TrueNAS side**: the snapshot-clone cron, the NFS shares, the snapshot tasks, and
  a periodic config export. TrueNAS has a middleware API: `midclt call` over ssh,
  driven from Ansible with a find-or-create pattern. Open questions: is ssh enabled
  on HexOS, and does HexOS (an appliance layer on TrueNAS) tolerate config changed
  outside its UI? The cron one-liner is the most fragile piece of the pipeline, so
  this is the most valuable item in this tier.

## Not worth it, or not possible

- PVE install and the `rpool` mirror (bare metal; the Proxmox automated installer
  `answer.toml` is the closest thing, and a different tool).
- HexOS install, pool, users and SMB/NFS shares in its UI (only a config export
  captures this).
- UniFi DHCP lease for CT 105 (no good module; keep it as a note).
- Hetzner sub-accounts (two accounts, set once).
- PVE major upgrades: keep them hand-driven, tmux plus checkpoints as on 2026-10-13.

## Suggested order

1. Host baseline play (the whole "Easy" tier). Removes most of "Host" in
   `docs/proxmox0.md`.
2. Fetch the TrueNAS config export automatically (weekly `midclt call config.save`,
   stored under the borg job). It backs up everything in the NAS tier at once, even
   what cannot be codified, and is a small step. Already on the to-do list as "save
   a TrueNAS config export", which is currently not in git or any backup.
3. TrueNAS cron, shares and snapshot tasks via `midclt`, after checking ssh and that
   HexOS tolerates it.
4. Guest definitions, in `--check` mode.
