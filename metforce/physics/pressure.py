from __future__ import annotations

import math
import pandas as pd

from metforce.physics.dew_point import dewpoint_from_t_rh  # computes Td [°C] from T/RH

DEFAULT_PRESSURE_PA = 101_325.0

def _pressure_from_elevation_pa(elevation_m: float | int) -> float:
    """Barometric fallback: pressure [Pa] from elevation [m], US Std Atmosphere."""
    h = float(elevation_m)
    return 101_325.0 * math.pow(1.0 - 2.25577e-5 * h, 5.25588)

def _resolve_pressure_pa(
    pressure_pa: float | pd.Series | None,
    *,
    like: pd.Series | None,
    elevation_m: float | int | None,
) -> float | pd.Series:
    """Prefer explicit pressure [Pa], else Series attrs in Pa/mbar, else barometric fallback, else SLP."""
    # 1) explicit kwarg (scalar or Series)
    if pressure_pa is not None:
        return pressure_pa if isinstance(pressure_pa, pd.Series) else float(pressure_pa)

    # 2) via Series attrs (Pa or mbar)
    if like is not None and hasattr(like, "attrs"):
        attrs = getattr(like, "attrs", {}) or {}
        if "pressure_pa" in attrs and attrs["pressure_pa"] is not None:
            val = attrs["pressure_pa"]
            return val if isinstance(val, pd.Series) else float(val)
        if "pressure_mbar" in attrs and attrs["pressure_mbar"] is not None:
            val = attrs["pressure_mbar"]
            if isinstance(val, pd.Series):
                return (val.astype(float) * 100.0).rename(getattr(val, "name", None))
            return float(val) * 100.0

    # 3) from elevation or SL pressure
    if elevation_m is not None:
        return _pressure_from_elevation_pa(elevation_m)

    return DEFAULT_PRESSURE_PA

def _resolve_temp_dew_c(
    *,
    temp_dew_c: float | pd.Series | None,
    temp_c: pd.Series | None,
    rh_percent: pd.Series | None,
    index: pd.DatetimeIndex,
) -> float | pd.Series | None:
    """Return dew‑point (°C) as scalar/Series aligned to index if available; else None."""
    if temp_dew_c is not None:
        if isinstance(temp_dew_c, pd.Series):
            return pd.Series(temp_dew_c, dtype=float).reindex(index)
        return float(temp_dew_c)
    if temp_c is not None and rh_percent is not None:
        td = dewpoint_from_t_rh(temp_c, rh_percent)  # returns Series [°C]
        return td.reindex(index)
    return None
