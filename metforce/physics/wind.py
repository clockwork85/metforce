from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def _to_numpy(x: Iterable) -> np.ndarray:
    """ convert pandas/array-like to a 1D float64 ndarray. """
    arr = np.asarray(x, dtype=float)
    if arr.ndim != 1:
        raise ValueError("speed and direction must be 1-D arrays")
    return arr


def vector_mean_from_samples(
        speed_mps: Iterable[float],
        from_dir_deg: Iterable[float],
        calm_threshold_mps: float = 0.2
) -> tuple[float, float]:
    """ Compute the vector-mean wind across samples in one bin """
    s = _to_numpy(speed_mps)
    th = _to_numpy(from_dir_deg)

    # Mask invalid samples (either NaN in speed or direction)
    valid = ~(np.isnan(s) | np.isnan(th))
    if not np.any(valid):
        return (float("nan"), float("nan"))

    s = s[valid]
    th = th[valid] * (math.pi / 180.0) # radians

    # components (met convention: FROM direction)
    u = -s * np.sin(th)
    v = -s * np.cos(th)

    # Vector mean of components
    u_bar = float(np.mean(u))
    v_bar = float(np.mean(v))

    mean_speed = math.hypot(u_bar, v_bar)
    mean_dir = (math.degrees(math.atan2(-u_bar, -v_bar)) % 360.0) if mean_speed > 0.0 else float("nan")

    if mean_speed < float(calm_threshold_mps):
        return (mean_speed, float("nan"))

    return mean_speed, mean_dir