from __future__ import annotations

import numpy as np


class FxLMSFilter:
    """Sample-by-sample feedforward FxLMS with normalized LMS update."""

    def __init__(
        self,
        filter_length: int,
        mu: float,
        epsilon: float,
        s_hat: np.ndarray,
        ref_delay: int = 0,
    ) -> None:
        self.L = filter_length
        self.mu = mu
        self.epsilon = epsilon
        self.base_mu = mu
        self.s_hat = np.asarray(s_hat, dtype=np.float64).ravel()
        self.M = self.s_hat.size

        self.w = np.zeros(self.L, dtype=np.float64)
        self.x_ext = np.zeros(self.L + self.M - 1, dtype=np.float64)

        self.ref_delay = max(0, int(ref_delay))
        self._delay_line: list[float] = []

    def set_mu(self, mu: float) -> None:
        self.mu = float(mu)

    def reset_state(self) -> None:
        self.w.fill(0.0)
        self.x_ext.fill(0.0)
        self._delay_line.clear()

    def _push_reference(self, x: float) -> None:
        if self.ref_delay > 0:
            self._delay_line.append(x)
            if len(self._delay_line) <= self.ref_delay:
                x = 0.0
            else:
                x = self._delay_line.pop(0)
        self.x_ext[1:] = self.x_ext[:-1]
        self.x_ext[0] = x

    def _filtered_regressor(self) -> np.ndarray:
        x_f = np.zeros(self.L, dtype=np.float64)
        for k in range(self.L):
            segment = self.x_ext[k : k + self.M]
            if segment.size == self.M:
                x_f[k] = np.dot(segment, self.s_hat)
        return x_f

    def process_block(
        self,
        x_ref: np.ndarray,
        e_err: np.ndarray,
        adapt: bool = True,
    ) -> tuple[np.ndarray, float]:
        n = x_ref.size
        y_out = np.zeros(n, dtype=np.float64)
        e_sq = 0.0

        for i in range(n):
            self._push_reference(float(x_ref[i]))
            e = float(e_err[i])
            y_out[i] = np.dot(self.w, self.x_ext[: self.L])
            e_sq += e * e

            if adapt:
                x_f = self._filtered_regressor()
                norm = float(np.dot(x_f, x_f)) + self.epsilon
                self.w += (self.mu / norm) * e * x_f

        e_rms = float(np.sqrt(e_sq / max(n, 1)))
        return y_out.astype(np.float32), e_rms


def generate_mls(length: int) -> np.ndarray:
    """MLS-like bipolar sequence via 15-bit LFSR (max period for identification)."""
    reg = 0x7FFF
    taps = 0x6000
    out = np.zeros(length, dtype=np.float32)
    for i in range(length):
        out[i] = 1.0 if (reg & 1) else -1.0
        fb = bin(reg & taps).count("1") % 2
        reg >>= 1
        if fb:
            reg |= 1 << 14
    return out


def estimate_fir_ls(x: np.ndarray, y: np.ndarray, filter_length: int) -> np.ndarray:
    """Least-squares FIR identification: y approximately equals x convolved with h."""
    n = min(x.size, y.size)
    if n < filter_length + 32:
        raise ValueError("Not enough samples for FIR identification")
    num_rows = n - filter_length + 1
    A = np.zeros((num_rows, filter_length), dtype=np.float64)
    for i in range(num_rows):
        A[i] = x[i : i + filter_length][::-1]
    d = y[filter_length - 1 : filter_length - 1 + num_rows]
    h, _, _, _ = np.linalg.lstsq(A, d, rcond=None)
    return h.astype(np.float64)


def cross_correlation_delay(x: np.ndarray, y: np.ndarray, max_lag: int) -> int:
    """Lag in samples: positive means reference leads error."""
    best_lag = 0
    best_val = -1.0
    x = x - np.mean(x)
    y = y - np.mean(y)
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            xs = x[: x.size - lag] if lag else x
            ys = y[lag:]
        else:
            xs = x[-lag:]
            ys = y[: y.size + lag]
        if xs.size < 32:
            continue
        denom = np.linalg.norm(xs) * np.linalg.norm(ys) + 1e-12
        val = abs(float(np.dot(xs, ys) / denom))
        if val > best_val:
            best_val = val
            best_lag = lag
    return best_lag