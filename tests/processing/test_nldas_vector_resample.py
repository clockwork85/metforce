# tests/processing/test_nldas_vector_resample.py
"""
What this file tests:
1) Vector-mean wind coarsening of a short time series with wrap-around headings.
2) The NLDAS coarsener combines vector wind with mean (scalars) and sum (precip)
   into a DataFrame aligned to the requested output cadence.

Why this matters:
- Naively averaging directions (e.g., 350°, 10°, 20°) is wrong: it gives ~126.7°.
  The vector-mean correctly returns ~6.7° and a slightly reduced speed.
- For merged pipelines, NLDAS often needs to coarsen (or match a different cadence).
  We want to ensure that, when coarsening is needed, wind uses vector means.
"""

import numpy as np
import pandas as pd
import pytest

from metforce.physics.wind import resample_wind_vector_mean
from metforce.processing.nldas2 import _coarsen_nldas2_df_to_date_range  # local helper

def _angle_close(a, b, atol=1e-2) -> bool:
    """Compare directions modulo 360°, using an absolute tolerance in degrees."""
    d = (a - b + 180.0) % 360.0 - 180.0
    return abs(d) <= atol

def test_resample_wind_vector_wraparound_coarsen():
    """
    Given three 10-min samples (5 m/s, headings 350°, 10°, 20°),
    coarsen to a single 30-min bin via vector-mean.
    Expect:
      speed ≈ 4.883 m/s (vector-mean reduces magnitude),
      direction ≈ 6.7° (resolves wrap-around near 0°/360° correctly).
    """
    idx = pd.date_range("2020-01-01 00:00", periods=3, freq="10min", tz="UTC")
    speed = pd.Series([5.0, 5.0, 5.0], index=idx, name="wind_speed")
    direction = pd.Series([350.0, 10.0, 20.0], index=idx, name="wind_direction")

    target = pd.date_range("2020-01-01 00:00", periods=1, freq="30min", tz="UTC")
    spd_vec, dir_vec = resample_wind_vector_mean(speed, direction, target, calm_threshold_mps=0.2)

    assert spd_vec.iloc[0] == pytest.approx(4.883, rel=1e-3, abs=1e-3), \
        "Vector-mean speed should drop below 5 m/s due to angular spread"
    assert _angle_close(dir_vec.iloc[0], 6.7, atol=1e-2), \
        "Vector-mean direction should resolve across 360° boundary to ~6.7°"

def test_coarsen_nldas2_df_vector_wind_mean_scalars_sum_precip():
    """
    Build a synthetic NLDAS-like hourly frame with:
      - wind_speed/wind_direction over 3 hours, wrapping around 0°,
      - pressure as a simple scalar,
      - precipitation as hourly amounts.
    Coarsen to a 3-hour bin:
      - wind should use vector-mean,
      - pressure should be a mean,
      - precipitation should be a sum.
    """
    # 3 hourly samples
    idx = pd.date_range("2020-01-01 00:00", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "wind_speed": [5.0, 5.0, 5.0],
        "wind_direction": [350.0, 10.0, 20.0],
        "pressure": [1010.0, 1012.0, 1011.0],
        "precipitation": [1.0, 2.0, 3.0],  # treat as 'mm per hour' values for this synthetic example
    }, index=idx)

    # target is a single 3-hour bin (coarsening)
    target = pd.date_range("2020-01-01 00:00", periods=1, freq="3h", tz="UTC")

    coarsened = _coarsen_nldas2_df_to_date_range(
        df, target, parameters=["wind_speed", "wind_direction", "pressure", "precipitation"],
        wind_avg_method="vector", calm_threshold_mps=0.2
    )

    # -- wind: vector-mean --
    got_spd = float(coarsened["wind_speed"].iloc[0])
    got_dir = float(coarsened["wind_direction"].iloc[0])
    assert got_spd == pytest.approx(4.883, rel=1e-3, abs=1e-3), \
        "Coarsened wind speed should match the vector-mean of three 5 m/s samples"
    assert _angle_close(got_dir, 6.7, atol=1e-2), \
        "Coarsened wind direction should be ~6.7° via vector-mean, not a naive ~126.7°"

    # -- scalars: mean --
    exp_pressure = (1010.0 + 1012.0 + 1011.0) / 3.0
    assert float(coarsened["pressure"].iloc[0]) == pytest.approx(exp_pressure, rel=1e-12), \
        "Non-wind scalar should be averaged when coarsening"

    # -- precipitation: sum --
    assert float(coarsened["precipitation"].iloc[0]) == pytest.approx(1.0 + 2.0 + 3.0, rel=1e-12), \
        "Precipitation should sum across the coarsening window"
