#!/usr/bin/env python3
"""Adaptive feedforward FxLMS noise cancellation loop."""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

import numpy as np

from audio_io import DuplexAudio
from config_load import ANC_DIR, load_config, resolve_path
from dsp import FxLMSFilter


class Watchdog:
    def __init__(self, cfg: dict) -> None:
        self.enabled = bool(cfg.get("watchdog_enabled", True))
        self.factor = float(cfg.get("watchdog_factor", 2.5))
        self.duration = float(cfg.get("watchdog_duration_seconds", 2.0))
        self.baseline_time = float(cfg.get("watchdog_baseline_seconds", 5.0))
        self.mu_min = float(cfg.get("mu_min", 1e-4))
        self.baseline: float | None = None
        self.bad_since: float | None = None

    def update(self, e_rms: float, filt: FxLMSFilter, t: float) -> None:
        if not self.enabled:
            return
        if self.baseline is None:
            if t < self.baseline_time:
                return
            self.baseline = max(e_rms, 1e-9)
            return
        threshold = self.baseline * self.factor
        if e_rms > threshold:
            if self.bad_since is None:
                self.bad_since = t
            elif t - self.bad_since >= self.duration:
                filt.set_mu(max(self.mu_min, filt.mu * 0.5))
                self.bad_since = None
        else:
            self.bad_since = None
            if filt.mu < filt.base_mu:
                filt.set_mu(min(filt.base_mu, filt.mu * 1.05))


def load_secondary(cfg: dict) -> np.ndarray:
    path = resolve_path(cfg, "secondary_path_file")
    if not path.is_file():
        print(f"Missing {path}. Run calibrate_secondary.py first.", file=sys.stderr)
        sys.exit(1)
    data = np.load(path)
    return np.asarray(data["s_hat"], dtype=np.float64).ravel()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FxLMS ANC")
    parser.add_argument("--config", type=Path, default=ANC_DIR / "config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Mute speaker output")
    parser.add_argument("--mu", type=float, default=None)
    parser.add_argument("--seconds", type=float, default=None, help="Stop after N seconds (default: run)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    s_hat = load_secondary(cfg)

    rate = int(cfg["rate"])
    block = int(cfg["block_size"])
    mu = float(args.mu if args.mu is not None else cfg["mu"])
    warmup = float(cfg.get("warmup_seconds", 3.0))
    max_out = float(cfg.get("max_output", 0.25))
    invert = bool(cfg.get("invert_output", True))
    ref_delay = int(cfg.get("ref_to_error_delay", 0))
    filt_len = int(cfg["filter_length"])

    audio = DuplexAudio(
        device=cfg["device"],
        rate=rate,
        channels=int(cfg["channels"]),
        block_size=block,
        ref_channel=int(cfg["ref_channel"]),
        error_channel=int(cfg["error_channel"]),
        ref_gain=float(cfg.get("ref_gain", 1.0)),
        error_gain=float(cfg.get("error_gain", 1.0)),
        playback_channels=int(cfg.get("playback_channels", 2)),
    )

    filt = FxLMSFilter(
        filter_length=filt_len,
        mu=mu,
        epsilon=float(cfg.get("epsilon", 1e-8)),
        s_hat=s_hat,
        ref_delay=ref_delay,
    )
    watchdog = Watchdog(cfg)

    stop = False

    def _sig(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    print(
        f"FxLMS started: rate={rate} block={block} L={filt_len} mu={mu} "
        f"dry_run={args.dry_run} warmup={warmup}s"
    )
    t0 = time.monotonic()
    block_dt = block / rate
    next_tick = t0
    blocks = 0

    try:
        while not stop:
            x_ref, e_err = audio.read_block()
            t = time.monotonic() - t0
            adapt = t >= warmup
            y, e_rms = filt.process_block(x_ref, e_err, adapt=adapt)
            if invert:
                y = -y
            if t < warmup:
                y = np.zeros_like(y)
            audio.write_output(y, max_output=max_out, dry_run=args.dry_run)
            watchdog.update(e_rms, filt, t)
            blocks += 1
            if blocks % 50 == 0:
                w_norm = float(np.linalg.norm(filt.w))
                print(
                    f"t={t:6.1f}s e_rms={e_rms:.6f} |w|={w_norm:.4f} mu={filt.mu:.5f} "
                    f"xruns={audio.xrun_count}",
                    flush=True,
                )
            if args.seconds is not None and t >= args.seconds:
                break
            next_tick += block_dt
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_tick = time.monotonic()
    finally:
        audio.write_output(np.zeros(block, dtype=np.float32), max_output=0.0)
        audio.close()
        print("Stopped (speaker muted).")


if __name__ == "__main__":
    main()