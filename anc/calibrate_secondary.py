#!/usr/bin/env python3
"""Identify secondary path S_hat: speaker -> error microphone."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from audio_io import DuplexAudio
from config_load import ANC_DIR, load_config, resolve_path
from dsp import estimate_fir_ls, generate_mls


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate secondary path (speaker to error mic)")
    parser.add_argument("--config", type=Path, default=ANC_DIR / "config.yaml")
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--amplitude", type=float, default=0.08)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    out_path = args.output or resolve_path(cfg, "secondary_path_file")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rate = int(cfg["rate"])
    block = int(cfg["block_size"])
    s_len = int(cfg["secondary_filter_length"])
    n_samples = int(args.seconds * rate)

    mls = generate_mls(n_samples)
    u = mls * float(args.amplitude)

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

    captured_u = np.zeros(n_samples, dtype=np.float32)
    captured_e = np.zeros(n_samples, dtype=np.float32)

    offset = 0
    try:
        print(f"Playing MLS on speaker for {args.seconds}s at amplitude {args.amplitude}...")
        while offset < n_samples:
            end = min(offset + block, n_samples)
            chunk = u[offset:end]
            if chunk.size < block:
                pad = np.zeros(block - chunk.size, dtype=np.float32)
                chunk = np.concatenate([chunk, pad])
            audio.write_output(chunk, max_output=1.0, dry_run=False)
            _x_ref, e_err = audio.read_block()
            captured_u[offset:end] = u[offset:end]
            captured_e[offset:end] = e_err[: end - offset]
            offset = end
        time.sleep(0.05)
    finally:
        audio.write_output(np.zeros(block, dtype=np.float32), max_output=0.0)
        audio.close()

    s_hat = estimate_fir_ls(captured_u, captured_e, s_len)
    np.savez(
        out_path,
        s_hat=s_hat,
        rate=rate,
        filter_length=s_len,
        amplitude=args.amplitude,
    )
    print(f"Saved secondary path ({s_len} taps) to {out_path}")
    print(f"Energy: {float(np.sum(s_hat**2)):.6e}, peak: {float(np.max(np.abs(s_hat))):.6f}")


if __name__ == "__main__":
    main()