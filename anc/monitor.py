#!/usr/bin/env python3
"""Monitor mic levels without adaptation (reference + error RMS)."""

from __future__ import annotations

import argparse
import signal
import time
from pathlib import Path

import numpy as np

from agent_log import agent_log
from audio_io import DuplexAudio
from config_load import ANC_DIR, load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor capture channels")
    parser.add_argument("--config", type=Path, default=ANC_DIR / "config.yaml")
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()

    cfg = load_config(args.config)
    block = int(cfg["block_size"])
    audio = DuplexAudio(
        device=cfg["device"],
        rate=int(cfg["rate"]),
        channels=int(cfg["channels"]),
        block_size=block,
        ref_channel=int(cfg["ref_channel"]),
        error_channel=int(cfg["error_channel"]),
        ref_gain=float(cfg.get("ref_gain", 1.0)),
        error_gain=float(cfg.get("error_gain", 1.0)),
    )

    stop = False

    def _sig(sig: int, _f: object) -> None:
        nonlocal stop
        stop = True
        # #region agent log
        agent_log(
            "C",
            "monitor.py:_sig",
            "SIGINT received",
            {"signum": sig},
        )
        # #endregion

    signal.signal(signal.SIGINT, _sig)

    t0 = time.monotonic()
    # #region agent log
    agent_log(
        "B",
        "monitor.py:main",
        "monitor start",
        {
            "device": cfg["device"],
            "seconds": args.seconds,
            "block_size": block,
            "rate": int(cfg["rate"]),
        },
    )
    # #endregion
    iteration = 0
    try:
        while not stop and (time.monotonic() - t0) < args.seconds:
            iteration += 1
            x_ref, e_err = audio.read_block()
            ref_rms = float(np.sqrt(np.mean(x_ref**2)))
            err_rms = float(np.sqrt(np.mean(e_err**2)))
            print(
                f"ref_rms={ref_rms:.6f} err_rms={err_rms:.6f} xruns={audio.xrun_count}",
                flush=True,
            )
            # #region agent log
            if iteration <= 3 or iteration % 50 == 0:
                agent_log(
                    "A",
                    "monitor.py:loop",
                    "before write_output",
                    {
                        "iteration": iteration,
                        "elapsed_s": round(time.monotonic() - t0, 3),
                        "stop": stop,
                        "ref_rms": ref_rms,
                        "xruns": audio.xrun_count,
                    },
                )
            # #endregion
            try:
                written = audio.write_output(
                    np.zeros(block, dtype=np.float32), max_output=0.0
                )
            except Exception as exc:
                # #region agent log
                agent_log(
                    "A",
                    "monitor.py:loop",
                    "write_output raised",
                    {
                        "iteration": iteration,
                        "elapsed_s": round(time.monotonic() - t0, 3),
                        "stop": stop,
                        "exc_type": type(exc).__name__,
                        "exc_str": str(exc),
                        "xruns": audio.xrun_count,
                    },
                )
                # #endregion
                raise
            # #region agent log
            if written < 0 or iteration <= 3:
                agent_log(
                    "E",
                    "monitor.py:loop",
                    "after write_output",
                    {"iteration": iteration, "written": written},
                )
            # #endregion
    finally:
        # #region agent log
        agent_log(
            "C",
            "monitor.py:finally",
            "monitor teardown",
            {
                "iteration": iteration,
                "stop": stop,
                "elapsed_s": round(time.monotonic() - t0, 3),
                "timed_out": (time.monotonic() - t0) >= args.seconds,
            },
        )
        # #endregion
        audio.close()


if __name__ == "__main__":
    main()