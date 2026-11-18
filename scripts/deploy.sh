#!/usr/bin/env bash
set -euo pipefail

PI_HOST="${PI_HOST:-pi@192.168.8.153}"
REMOTE_DIR="${REMOTE_DIR:-/home/pi/anc}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Syncing ANC to ${PI_HOST}:${REMOTE_DIR} ..."
rsync -avz --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "${REPO_ROOT}/anc/" "${PI_HOST}:${REMOTE_DIR}/"

rsync -avz "${REPO_ROOT}/requirements.txt" "${PI_HOST}:${REMOTE_DIR}/requirements.txt"
rsync -avz "${REPO_ROOT}/scripts/anc.service" "${PI_HOST}:${REMOTE_DIR}/anc.service"

echo "Installing Python dependencies on Pi ..."
ssh "${PI_HOST}" bash -s <<EOF
set -euo pipefail
if ! dpkg -s python3-alsaaudio >/dev/null 2>&1; then
  echo "Note: python3-alsaaudio not installed; using arecord/aplay fallback."
  echo "For lower latency, run on the Pi: sudo apt install python3-alsaaudio"
fi
cd "${REMOTE_DIR}"
if dpkg -s python3-alsaaudio >/dev/null 2>&1; then
  python3 -m venv --system-site-packages .venv
else
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
chmod +x calibrate_secondary.py measure_delay.py run_anc.py monitor.py
echo "Deploy complete. Try: ssh ${PI_HOST} 'cd ${REMOTE_DIR} && .venv/bin/python monitor.py --seconds 5'"
EOF