from __future__ import annotations

import os
import subprocess
import threading
from collections import deque

import numpy as np

from audio_io import S32_MAX


class DuplexAudio:
    """ALSA capture/playback via arecord/aplay (no pyalsaaudio required)."""

    def __init__(
        self,
        device: str,
        rate: int,
        channels: int,
        block_size: int,
        ref_channel: int,
        error_channel: int,
        ref_gain: float = 1.0,
        error_gain: float = 1.0,
        playback_channels: int = 2,
    ) -> None:
        self.rate = rate
        self.block_size = block_size
        self.ref_channel = ref_channel
        self.error_channel = error_channel
        self.ref_gain = ref_gain
        self.error_gain = error_gain
        self.playback_channels = playback_channels
        self.xrun_count = 0
        self._frame_bytes = block_size * channels * 4
        self._queue: deque[bytes] = deque(maxlen=64)
        self._lock = threading.Lock()
        self._stop = threading.Event()

        rec_cmd = [
            "arecord",
            "-q",
            "-D",
            device,
            "-f",
            "S32_LE",
            "-r",
            str(rate),
            "-c",
            str(channels),
            "--period-size",
            str(block_size),
            "-t",
            "raw",
        ]
        play_cmd = [
            "aplay",
            "-q",
            "-D",
            device,
            "-f",
            "S32_LE",
            "-r",
            str(rate),
            "-c",
            str(channels),
            "--period-size",
            str(block_size),
            "-t",
            "raw",
        ]
        self._rec = subprocess.Popen(
            rec_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._play = subprocess.Popen(
            play_cmd,
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        assert self._rec.stdout is not None
        while not self._stop.is_set():
            chunk = self._rec.stdout.read(self._frame_bytes)
            if not chunk or len(chunk) < self._frame_bytes:
                if not self._stop.is_set():
                    self.xrun_count += 1
                continue
            with self._lock:
                self._queue.append(chunk)

    def _bytes_to_stereo(self, data: bytes) -> np.ndarray:
        raw = np.frombuffer(data, dtype=np.int32).reshape(-1, 2)
        return (raw.astype(np.float64) / S32_MAX).astype(np.float32)

    def read_block(self) -> tuple[np.ndarray, np.ndarray]:
        deadline = 2.0
        import time

        t0 = time.monotonic()
        data = b""
        while time.monotonic() - t0 < deadline:
            with self._lock:
                if self._queue:
                    data = self._queue.popleft()
                    break
            time.sleep(0.001)
        if not data:
            self.xrun_count += 1
            stereo = np.zeros((self.block_size, 2), dtype=np.float32)
        else:
            stereo = self._bytes_to_stereo(data)
        x_ref = stereo[:, self.ref_channel] * self.ref_gain
        e_err = stereo[:, self.error_channel] * self.error_gain
        return x_ref, e_err

    def write_output(
        self,
        y_mono: np.ndarray,
        max_output: float,
        dry_run: bool = False,
    ) -> int:
        y = np.clip(y_mono, -max_output, max_output)
        if dry_run:
            y = np.zeros_like(y)
        if self.playback_channels == 2:
            stereo = np.column_stack([y, y])
        else:
            stereo = y.reshape(-1, 1)
        pcm = (stereo * S32_MAX).astype(np.int32).tobytes()
        assert self._play.stdin is not None
        try:
            self._play.stdin.write(pcm)
            self._play.stdin.flush()
        except BrokenPipeError:
            self.xrun_count += 1
            return -1
        return len(pcm)

    def close(self) -> None:
        self._stop.set()
        if self._play.stdin:
            try:
                self._play.stdin.close()
            except OSError:
                pass
        for proc in (self._rec, self._play):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
        if self._reader.is_alive():
            self._reader.join(timeout=2)