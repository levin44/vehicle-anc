# Command-line tools

Run on the Pi from `/home/pi/anc` (or your deploy target) with the project venv activated:

```bash
source .venv/bin/activate
```

Scripts are also executable after deploy (`chmod +x` in `deploy.sh`).

## `monitor.py`

Print reference and error RMS without playing anti-noise.

```bash
python monitor.py [--config PATH] [--seconds 10]
```

Verify channel assignment: stimulus near reference mic should move `ref_rms`; near error mic should move `err_rms`.

## `measure_delay.py`

Inject MLS on the speaker, correlate at the error mic, estimate acoustic delay for feedforward alignment.

```bash
python measure_delay.py [--config PATH] [--seconds 3] [--amplitude 0.12] [--write-config]
```

Use `--write-config` to persist `ref_to_error_delay` in `config.yaml`.

## `calibrate_secondary.py`

Estimate speaker → error microphone FIR (`s_hat`) and save NPZ.

```bash
python calibrate_secondary.py [--config PATH] [--seconds 4] [--amplitude 0.08] [--output PATH]
```

Use low `--amplitude`; keep error mic in its final position. Default output is `secondary_path_file` from config.

## `run_anc.py`

Closed-loop FxLMS.

```bash
python run_anc.py [--config PATH] [--dry-run] [--mu FLOAT] [--seconds N]
```

| Flag | Purpose |
|------|---------|
| `--dry-run` | Adapt (after warmup) but do not send audio to speaker — safe CPU/xrun check |
| `--mu` | Override config step size for this run |
| `--seconds` | Auto-stop after N seconds (omit for continuous / systemd) |

Periodic logs include `e_rms`, filter norm `|w|`, current `mu`, and `xruns`.

## Typical order

1. `monitor.py`
2. `measure_delay.py --write-config`
3. `calibrate_secondary.py`
4. `run_anc.py --dry-run --seconds 30`
5. `run_anc.py`