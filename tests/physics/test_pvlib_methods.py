# tests/physics/test_pvlib_methods.py
"""
What this file tests:
1) Every supported pvlib split method (disc, dirint, dirindex, erbs) runs against
   the installed pvlib and returns finite, positive beam irradiance for sunny hours.
2) The full split path keeps a real beam when the station pressure has a gap.

Why this matters:
- disc and erbs take their timestamps as `datetime_or_doy`; passing `times=` made
  them raise TypeError on every call.
- pvlib's dirint returns zero DNI for every hour when any pressure value is NaN.
"""

import numpy as np
import pandas as pd
import pytest

from metforce.physics.solar_irradiance import decompose_shortwave
from metforce.processing.derived_data import process_global_data

IDX = pd.date_range("2025-06-29 16:00", periods=3, freq="1h", tz="UTC")
GHI = pd.Series([600.0, 750.0, 820.0], index=IDX)
ZENITH = pd.Series([40.0, 30.0, 22.0], index=IDX)


@pytest.mark.parametrize("method", ["disc", "dirint", "dirindex", "erbs"])
def test_every_split_method_runs(method):
    out = decompose_shortwave(
        ghi=GHI, zenith=ZENITH, method=method,
        latitude=31.0, longitude=-93.1, elevation_m=94.0, pressure_pa=100800.0,
    )
    dni = out["direct_shortwave"]
    dhi = out["diffuse_shortwave"]
    cosz = np.cos(np.radians(ZENITH))
    assert np.isfinite(dni).all() and (dni > 0).all()
    assert (dni * cosz <= GHI + 1e-6).all()
    assert (dhi >= 0).all()


def test_station_pressure_gap_keeps_the_beam():
    params = {
        "global_shortwave": {"source": "met"},
        "zenith": {"source": "pvlib"},
        "pressure": {"source": "met"},
        "direct_shortwave": {"source": "pvlib_dirint"},
        "diffuse_shortwave": {"source": "pvlib_dirint"},
    }
    frames = {
        "met": pd.DataFrame({"global_shortwave": GHI, "pressure": [1008.0, np.nan, 1006.0]}),
        "pvlib": pd.DataFrame({"zenith": ZENITH}),
    }
    out = process_global_data(params, IDX, frames, latitude=31.0, longitude=-93.1, elevation=94.0)
    assert (out["direct_shortwave"] > 0).all()
