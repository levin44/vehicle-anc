# Development workflow

This repo is edited on a dev machine and deployed to the Pi; only `anc/` is synced by default (see `scripts/deploy.sh`).

## Dev machine setup

```bash
cd /path/to/pi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements-dev.txt` includes `pyalsaaudio` for optional local ALSA testing on Linux. On a machine without the Voice HAT, you can still run unit-level checks on `dsp.py` (numpy/scipy only); full duplex requires Pi hardware or compatible ALSA devices.

## Deploy to the Pi

```bash
./scripts/deploy.sh
```

Environment overrides:

| Variable | Default | Meaning |
|----------|---------|---------|
| `PI_HOST` | `pi@192.168.8.153` | SSH target |
| `REMOTE_DIR` | `/home/pi/anc` | Remote project root |

Example:

```bash
PI_HOST=pi@my-pi.local REMOTE_DIR=/home/pi/anc ./scripts/deploy.sh
```

Deploy:

- Rsyncs `anc/` (excludes `.venv`, `__pycache__`)
- Copies `requirements.txt` and `anc.service`
- Creates venv with `--system-site-packages` when `python3-alsaaudio` is installed on the Pi
- Installs pip dependencies

## Remote operations

```bash
ssh pi@192.168.8.153 'cd /home/pi/anc && .venv/bin/python monitor.py --seconds 5'
journalctl -u anc -f    # on the Pi, if using systemd
```

Install the service from the synced unit file:

```bash
sudo cp /home/pi/anc/anc.service /etc/systemd/system/anc.service
sudo systemctl daemon-reload
sudo systemctl enable --now anc
```

## Editing safely

- **Algorithm changes:** `anc/dsp.py`, `anc/run_anc.py` — test with `--dry-run` before live speaker.
- **I/O changes:** `anc/audio_io.py` / `audio_io_subprocess.py` — watch `xruns` in `run_anc.py` logs.
- **Config defaults:** keep `anc/config.yaml` compatible with existing NPZ calibration files on deployed Pis.

## Documentation map

- [ARCHITECTURE.md](ARCHITECTURE.md) — signal flow and module roles
- [CONFIGURATION.md](CONFIGURATION.md) — `config.yaml` reference
- [CLI.md](CLI.md) — script flags and calibration order
- [../README.md](../README.md) — hardware, quick start, limitations