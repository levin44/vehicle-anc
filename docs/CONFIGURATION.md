# Configuration reference

All runtime scripts read [`anc/config.yaml`](../anc/config.yaml) unless you pass `--config`.

Paths in config are relative to the `anc/` directory unless absolute.

## ALSA / I/O

| Key | Type | Description |
|-----|------|-------------|
| `device` | string | ALSA PCM name (default `hw:1,0` for Voice HAT) |
| `rate` | int | Sample rate Hz (48000) |
| `channels` | int | Capture channels (2 = stereo mics) |
| `format` | string | Capture format (`S32_LE`) |
| `ref_channel` | int | 0-based index for reference mic |
| `error_channel` | int | 0-based index for error mic |
| `ref_gain` | float | Scale reference after int32 → float normalization |
| `error_gain` | float | Scale error channel |
| `playback_channels` | int | Speaker outputs driven (2 = both HAT channels) |
| `invert_output` | bool | Negate anti-noise; flip if cancellation becomes reinforcement |

Use `monitor.py` and clap near each mic to confirm `ref_channel` and `error_channel` are not swapped.

## FxLMS

| Key | Type | Description |
|-----|------|-------------|
| `block_size` | int | Samples per audio block (latency vs CPU tradeoff) |
| `filter_length` | int | Adaptive FIR length `L` (more taps → more low-frequency rejection, more CPU) |
| `secondary_filter_length` | int | Length used when fitting `ŝ` in calibration |
| `mu` | float | Normalized LMS step size (reduce if unstable or ringing) |
| `epsilon` | float | Normalization floor in LMS denominator |
| `max_output` | float | Peak anti-noise amplitude (0–1 scale before ALSA) |
| `warmup_seconds` | float | No adaptation or speaker drive until elapsed |
| `ref_to_error_delay` | int | Sample delay applied to reference (set via `measure_delay.py`) |
| `secondary_path_file` | string | NPZ with array `s_hat` (from `calibrate_secondary.py`) |

## Watchdog

| Key | Type | Description |
|-----|------|-------------|
| `watchdog_enabled` | bool | Enable automatic `mu` reduction on sustained high error |
| `watchdog_baseline_seconds` | float | Time before baseline RMS is captured |
| `watchdog_factor` | float | Trip threshold = baseline × this factor |
| `watchdog_duration_seconds` | float | How long above threshold before reducing `mu` |
| `mu_min` | float | Lower bound for step size after reductions |

## Tuning guide

| Symptom | Suggested change |
|---------|------------------|
| Noise increases | Toggle `invert_output`; reduce `mu` |
| Slow or weak cancellation | Slightly increase `mu` or `filter_length` (watch CPU/xruns) |
| Oscillation / pumping | Lower `mu`; check mic placement and secondary calibration |
| Low-frequency hum weak | Increase `filter_length`; ensure secondary path was taken at final geometry |
| ALSA xruns | Increase `block_size`; install `python3-alsaaudio`; reduce load on Pi |
| Wrong mic mapping | Swap `ref_channel` / `error_channel` |

Re-run `measure_delay.py --write-config` and `calibrate_secondary.py` after moving mics or the speaker.