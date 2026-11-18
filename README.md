# Raspberry Pi feedforward ANC (FxLMS)

Adaptive noise cancellation on a Pi 4 with two ICS-43434 I2S microphones (reference + error) and a Google Voice HAT speaker, using **Filtered-x LMS**.

## Hardware

- `dtoverlay=googlevoicehat-soundcard`, `dtparam=i2s=on`
- Stereo capture: reference and error on **L/R** (`hw:1,0`, S32_LE, 48 kHz)
- [Adafruit I2S MEMS wiring](https://learn.adafruit.com/adafruit-i2s-mems-microphone-breakout/raspberry-pi-wiring-test)

**Placement**

- Reference mic: near the noise source, not in the speaker’s direct path
- Error mic: in the zone you want quiet
- Keep geometry fixed after calibrating the secondary path

## Quick start (on the Pi)

```bash
cd /home/pi/anc
python3 -m venv .venv
source .venv/bin/activate
sudo apt install python3-alsaaudio
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Deploy from dev machine (see below) syncs `anc/` and installs dependencies.

### 1. Check microphones

```bash
python3 monitor.py --seconds 15
```

Clap near each mic; confirm `ref_rms` vs `err_rms` match `ref_channel` / `error_channel` in `config.yaml` (swap `ref_channel` and `error_channel` if reversed).

### 2. Measure reference–error delay

```bash
python3 measure_delay.py --write-config
```

### 3. Calibrate secondary path (speaker → error mic)

Low speaker volume; error mic in final position.

```bash
python3 calibrate_secondary.py --seconds 4 --amplitude 0.08
```

Writes `data/secondary_path.npz`.

### 4. Run ANC

```bash
python3 run_anc.py --dry-run --seconds 30   # no speaker output, check CPU / xruns
python3 run_anc.py                          # live adaptation
```

- **Anti-noise sign:** if noise *increases*, set `invert_output: false` in `config.yaml`.
- **Stability:** lower `mu` (e.g. `0.003`); raise `filter_length` for low-frequency hum.
- **Stop:** Ctrl+C or `systemctl stop anc` (output is muted on exit).

## Deploy from dev workspace

```bash
./scripts/deploy.sh
```

Defaults: `pi@192.168.8.153`, remote `/home/pi/anc`.

## systemd

```bash
sudo cp /home/pi/anc/anc.service /etc/systemd/system/anc.service
sudo systemctl daemon-reload
sudo systemctl enable --now anc
```

## Configuration

Edit [`anc/config.yaml`](anc/config.yaml): `mu`, `filter_length`, `max_output`, channel map, watchdog.

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | FxLMS signal flow, modules, watchdog |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | `config.yaml` keys and tuning |
| [docs/CLI.md](docs/CLI.md) | `monitor`, `measure_delay`, calibrate, `run_anc` |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Venv, `deploy.sh`, systemd, env vars |

## Limitations

Best for **tonal / repetitive** noise (fans, hum). Latency and filter length limit broadband cancellation to a small zone (tens of cm).