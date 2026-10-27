#!/usr/bin/env bash
# Install only the pinned CLI locally; this does not install the in-cluster server.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$ROOT/setenv.sh"
case "$(uname -s)" in Linux) platform=linux ;; Darwin) platform=darwin ;; *) echo 'Unsupported OS; install Velero CLI manually.' >&2; exit 1 ;; esac
case "$(uname -m)" in x86_64|amd64) arch=amd64 ;; arm64|aarch64) arch=arm64 ;; *) echo 'Unsupported CPU architecture.' >&2; exit 1 ;; esac
folder="velero-$VELERO_VERSION-$platform-$arch"
archive="$folder.tar.gz"
install_dir="$ROOT/.tools/$folder"
if [[ -x "$install_dir/velero" ]] && "$install_dir/velero" version --client-only | grep -F "Version: $VELERO_VERSION" >/dev/null; then
  printf '%s\n' "$install_dir/velero"
  exit 0
fi
for tool in curl tar python3; do command -v "$tool" >/dev/null || { echo "Missing required installer tool: $tool" >&2; exit 1; }; done
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT
base="https://github.com/velero-io/velero/releases/download/$VELERO_VERSION"
echo "Installing Velero CLI $VELERO_VERSION locally for $platform/$arch..." >&2
curl -fLsS "$base/$archive" -o "$workdir/$archive"
curl -fLsS "$base/CHECKSUM" -o "$workdir/CHECKSUM"
python3 - "$workdir" "$archive" <<'PY'
import hashlib
from pathlib import Path
import sys
folder, name = Path(sys.argv[1]), sys.argv[2]
entries = [line.split() for line in (folder / 'CHECKSUM').read_text().splitlines() if line.strip()]
expected = next((parts[0] for parts in entries if len(parts) == 2 and parts[1].lstrip('*') == name), None)
if expected is None or hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
    raise SystemExit('Velero download checksum verification failed')
PY
tar -xzf "$workdir/$archive" -C "$workdir"
mkdir -p "$install_dir"
install -m 755 "$workdir/$folder/velero" "$install_dir/velero"
"$install_dir/velero" version --client-only | grep -F "Version: $VELERO_VERSION" >/dev/null
printf '%s\n' "$install_dir/velero"
