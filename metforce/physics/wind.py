from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd


def _to_numpy(x: Iterable) -> np.ndarray:
    """ convert pandas/array-like to a 1D float64 ndarray. """
    arr = np.asarray(x, dtype=float)
    if arr.ndim != 1:
        raise ValueError("speed and direction must be 1-D arrays")
    return arr

def _spd_dir_to_uv(speed: pd.Series, from_dir_deg: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Convert meteorological FROM-direction (deg) + speed (m/s) → components u (east), v (north)."""
    th = np.deg2rad(from_dir_deg.astype(float))
    u = -speed.astype(float) * np.sin(th)
    v = -speed.astype(float) * np.cos(th)
    return u, v

def _uv_to_spd_dir(u: pd.Series, v: pd.Series, calm_threshold_mps: float) -> tuple[pd.Series, pd.Series]:
    """Convert components → (speed, FROM-direction); calm bins give NaN for direction."""
    spd = np.hypot(u, v)
    # FROM-direction, degrees clockwise from North
    deg = (np.degrees(np.arctan2(-u, -v)) % 360.0)
    deg = deg.where(spd >= float(calm_threshold_mps), np.nan)
    return spd, deg


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

def resample_wind_vector_mean(
    speed: pd.Series,
    from_dir_deg: pd.Series,
    target_index: pd.DatetimeIndex,
    calm_threshold_mps: float = 0.2,
) -> tuple[pd.Series, pd.Series]:
    """
    Resample/aggregate wind time series onto `target_index` using *vector means*.

    What this does:
    - Converts each sample (S, θ_from) → (u, v) components.
    - Averages u and v over each resampling bin to the `target_index.freq`.
    - Converts the averaged (u, v) back to (S_vec, θ_vec_from) per bin.
    - Sets direction to NaN in "calm" bins (speed < `calm_threshold_mps`).

    Notes:
    - Designed for *coarsening* (e.g., 10‑min → 30‑min, hourly → 3‑hour).
      If the target freq equals the source freq, values are unchanged.
      For upsampling (finer target), we return a time-mean per bin which
      is typically not what you want; use interpolation if you later need it.
    """
    # Convert to components at native cadence
    u, v = _spd_dir_to_uv(speed, from_dir_deg)

    # Average components on the target cadence
    out_freq = target_index.freq
    if out_freq is None:
        raise ValueError("target_index must carry a defined .freq")

    u_bar = u.resample(out_freq).mean().reindex(target_index)
    v_bar = v.resample(out_freq).mean().reindex(target_index)

    # Convert back to speed/from-direction
    spd_vec, dir_vec = _uv_to_spd_dir(u_bar, v_bar, calm_threshold_mps)
    return spd_vec, dir_vec