#!/usr/bin/env python3
"""Measure reference-to-error acoustic delay via cross-correlation."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import yaml

from audio_io import DuplexAudio
from config_load import ANC_DIR, load_config
from dsp import generate_mls, cross_correlation_delay


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure ref_to_error_delay")
    parser.add_argument("--config", type=Path, default=ANC_DIR / "config.yaml")
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--amplitude", type=float, default=0.12)
    parser.add_argument("--write-config", action="store_true", help="Update config.yaml with measured delay")
    args = parser.parse_args()

    cfg = load_config(args.config)
    rate = int(cfg["rate"])
    block = int(cfg["block_size"])
    n_samples = int(args.seconds * rate)
    probe = generate_mls(n_samples) * float(args.amplitude)

    audio = DuplexAudio(
        device=cfg["device"],
        rate=rate,
        channels=int(cfg["channels"]),
        block_size=block,
        ref_channel=int(cfg["ref_channel"]),
        error_channel=int(cfg["error_channel"]),
        ref_gain=float(cfg.get("ref_gain", 1.0)),
        error_gain=float(cfg.get("error_gain", 1.0)),
    )

    ref = np.zeros(n_samples, dtype=np.float32)
    err = np.zeros(n_samples, dtype=np.float32)
    offset = 0
    try:
        while offset < n_samples:
            end = min(offset + block, n_samples)
            chunk = probe[offset:end]
            if chunk.size < block:
                chunk = np.pad(chunk, (0, block - chunk.size))
            audio.write_output(chunk, max_output=1.0)
            x_ref, e_err = audio.read_block()
            ref[offset:end] = x_ref[: end - offset]
            err[offset:end] = e_err[: end - offset]
            offset = end
    finally:
        audio.write_output(np.zeros(block, dtype=np.float32), max_output=0.0)
        audio.close()

    max_lag = int(rate * 0.05)
    lag = cross_correlation_delay(ref, err, max_lag)
    delay = max(0, lag)
    print(f"Estimated ref_to_error_delay: {delay} samples ({delay / rate * 1000:.2f} ms)")

    if args.write_config:
        cfg_path = Path(args.config)
        with cfg_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["ref_to_error_delay"] = delay
        with cfg_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        print(f"Updated {cfg_path}")
    else:
        print("Re-run with --write-config to save into config.yaml")


if __name__ == "__main__":
    main()