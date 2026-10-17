#!/usr/bin/env python3

# Builds data/certs.ar, the certificate bundle used by the firmware, from the
# Mozilla trusted CA list published by the CCADB.
#
# Usage: python3 get_moz_certs.py [--tls-only] [--output PATH]
#
# Needs `openssl` and `ar` (binutils, or the xtensa one shipped with PlatformIO).
# Upload the result to a device with `pio run -t uploadfs`, or publish it on the
# certificate update server for devices to fetch themselves.
#
# Originally by Earle F. Philhower, III. Released to the public domain.
import argparse
import csv
import io
import subprocess
import sys
import tempfile
from pathlib import Path
from shutil import which
from urllib.request import urlopen

MOZ_URL = "https://ccadb.my.salesforce-sites.com/mozilla/IncludedCACertificateReportPEMCSV"
MIN_CERTS = 20  # Fewer than this means the report format changed, not that Mozilla dropped CAs

project_dir = Path(__file__).resolve().parent

parser = argparse.ArgumentParser(description="Generate the certificate bundle")
parser.add_argument("--tls-only", action="store_true", help="Only include roots trusted for websites (smaller)")
parser.add_argument("--output", type=Path, default=project_dir / "data" / "certs.ar")
args = parser.parse_args()
args.output = args.output.resolve()

# Prefer the toolchain's ar if PlatformIO is installed, else the system one
ar_path = None
for candidate in (Path.home() / ".platformio/packages/toolchain-xtensa/bin/xtensa-lx106-elf-ar",):
    if candidate.is_file():
        ar_path = str(candidate)
ar_path = ar_path or which("ar")
if ar_path is None:
    sys.exit("You need `ar` (binutils) in PATH")
if which("openssl") is None:
    sys.exit("You need `openssl` in PATH")

print("Generating certificate store from mozilla trusted certificates")

csv_text = urlopen(MOZ_URL, timeout=60).read().decode("utf-8")
pems = []
for row in csv.DictReader(io.StringIO(csv_text)):
    if args.tls_only and "Websites" not in row["Trust Bits"]:
        continue
    pems.append(row["PEM Info"].strip().strip("'"))

with tempfile.TemporaryDirectory() as tmp:
    der_files = []
    for pem in pems:
        der = Path(tmp) / f"ca_{len(der_files):03d}.der"
        result = subprocess.run(["openssl", "x509", "-inform", "PEM", "-outform", "DER", "-out", str(der)],
                                input=pem.encode(), capture_output=True)
        if result.returncode == 0 and der.exists():
            der_files.append(der)
        else:
            print(f"Skipping a certificate that failed to convert: {result.stderr.decode().strip()}")

    if len(der_files) < MIN_CERTS:
        sys.exit(f"Only {len(der_files)} certificates found, refusing to write a bundle")

    # Build next to the target and rename, so a failure doesn't destroy the old bundle
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = args.output.with_suffix(".tmp")
    tmp_out.unlink(missing_ok=True)
    # D: no timestamps/owners in the archive, so the same certificates always give the same file
    subprocess.run([ar_path, "qD", str(tmp_out)] + [d.name for d in der_files], cwd=tmp, check=True,
                   capture_output=True)
    # Leave an identical file alone, so its mtime (and a web server's ETag for it) only changes with the content
    if args.output.exists() and args.output.read_bytes() == tmp_out.read_bytes():
        tmp_out.unlink()
        print(f"\n{len(der_files)} certificates, {args.output} is unchanged\n")
        sys.exit(0)
    tmp_out.replace(args.output)

print(f"\nFetched {len(der_files)} certificates, wrote {args.output} ({args.output.stat().st_size} bytes)\n")
