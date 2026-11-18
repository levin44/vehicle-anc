from __future__ import annotations

import numpy as np

from agent_log import agent_log

S32_MAX = 2**31

try:
    import alsaaudio as _alsaaudio
except ImportError:  # pragma: no cover
    _alsaaudio = None

if _alsaaudio is None:
    from audio_io_subprocess import DuplexAudio as _SubDuplex

    DuplexAudio = _SubDuplex
else:

    class DuplexAudio:  # type: ignore[no-redef]
        """Full-duplex capture/playback on a single ALSA PCM (Voice HAT)."""

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
            self._agent_write_i = 0

            self._pcm = _alsaaudio.PCM(
                type=_alsaaudio.PCM_CAPTURE,
                mode=_alsaaudio.PCM_NORMAL,
                device=device,
            )
            self._pcm_out = _alsaaudio.PCM(
                type=_alsaaudio.PCM_PLAYBACK,
                mode=_alsaaudio.PCM_NORMAL,
                device=device,
            )

            for pcm in (self._pcm, self._pcm_out):
                pcm.setchannels(channels)
                pcm.setrate(rate)
                pcm.setformat(_alsaaudio.PCM_FORMAT_S32_LE)
                pcm.setperiodsize(block_size)

        _PLAYBACK_BAD_STATES = (
            _alsaaudio.PCM_STATE_XRUN,
            _alsaaudio.PCM_STATE_SUSPENDED,
            _alsaaudio.PCM_STATE_DISCONNECTED,
        )

        def _playback_recover_if_needed(self, reason: str) -> bool:
            try:
                state = self._pcm_out.state()
            except _alsaaudio.ALSAAudioError:
                return False
            if state not in self._PLAYBACK_BAD_STATES:
                return False
            try:
                self._pcm_out.drop()
            except _alsaaudio.ALSAAudioError:
                pass
            self.xrun_count += 1
            # #region agent log
            agent_log(
                "B",
                "audio_io.py:_playback_recover_if_needed",
                "playback recovered after xrun",
                {"reason": reason, "prior_state": state, "xrun_count": self.xrun_count},
            )
            # #endregion
            return True

        @staticmethod
        def _bytes_to_stereo(data: bytes, channels: int) -> np.ndarray:
            if not data:
                return np.zeros((0, channels), dtype=np.float32)
            raw = np.frombuffer(data, dtype=np.int32)
            if raw.size % channels != 0:
                raw = raw[: raw.size - (raw.size % channels)]
            frames = raw.reshape(-1, channels).astype(np.float64)
            frames /= S32_MAX
            return frames.astype(np.float32)

        def read_block(self) -> tuple[np.ndarray, np.ndarray]:
            length, data = self._pcm.read()
            if length < 0:
                self.xrun_count += 1
                # #region agent log
                agent_log(
                    "A",
                    "audio_io.py:read_block",
                    "capture xrun",
                    {"length": length, "xrun_count": self.xrun_count},
                )
                # #endregion
                data = b""
            stereo = self._bytes_to_stereo(data, 2)
            if stereo.shape[0] < self.block_size:
                pad = np.zeros((self.block_size - stereo.shape[0], 2), dtype=np.float32)
                stereo = np.vstack([stereo, pad])
            elif stereo.shape[0] > self.block_size:
                stereo = stereo[: self.block_size]
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
            pcm = (stereo * S32_MAX).astype(np.int32)
            buf = pcm.tobytes()
            self._agent_write_i += 1
            # #region agent log
            if self._agent_write_i <= 3 or self._agent_write_i % 50 == 0:
                try:
                    out_state = self._pcm_out.state()
                except Exception as exc:
                    out_state = f"state_error:{exc}"
                agent_log(
                    "B",
                    "audio_io.py:write_output",
                    "pre-write playback",
                    {
                        "write_i": self._agent_write_i,
                        "buf_bytes": len(buf),
                        "out_state": out_state,
                    },
                )
            # #endregion
            self._playback_recover_if_needed("pre_write")
            try:
                written = self._pcm_out.write(buf)
            except _alsaaudio.ALSAAudioError as exc:
                # #region agent log
                agent_log(
                    "A",
                    "audio_io.py:write_output",
                    "playback write exception",
                    {
                        "exc_type": type(exc).__name__,
                        "exc_str": str(exc),
                        "buf_bytes": len(buf),
                    },
                )
                # #endregion
                self._playback_recover_if_needed("write_exception")
                written = self._pcm_out.write(buf)
            if written < 0:
                # #region agent log
                agent_log(
                    "E",
                    "audio_io.py:write_output",
                    "playback negative write",
                    {"written": written, "xrun_count": self.xrun_count},
                )
                # #endregion
                self._playback_recover_if_needed("negative_write")
                written = self._pcm_out.write(buf)
            return written

        def close(self) -> None:
            # #region agent log
            agent_log("D", "audio_io.py:close", "closing pcm", {})
            # #endregion
            self._pcm.close()
            self._pcm_out.close()