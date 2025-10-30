import numpy as np
import pandas as pd

from metforce.physics.solar_irradiance import decompose_shortwave
from metforce.processing.derived_data import process_global_data
import pytest

def test_dirindex_energy_closure_basic():
    # Simple midday-ish slice
    idx = pd.date_range("2024-06-21 17:00", periods=4, freq="15min", tz="UTC")  # pick something sunny
    # Build a plausible GHI curve (W m-2); keep it synthetic and positive
    ghi = pd.Series([700, 750, 730, 680], index=idx, name="ghi")
    # Zenith ~ 25-35 deg
    zen = pd.Series([35, 32, 30, 28], index=idx, name="zenith")

    out = decompose_shortwave(
        ghi, zen, "dirindex",
        latitude=35.0, longitude=-106.6, elevation_m=1600.0
    )
    dni = out["direct_shortwave"]
    dhi = out["diffuse_shortwave"]
    cosz = np.cos(np.radians(zen))

    # Energy closure: GHI ≈ DNI*cosZ + DHI
    np.testing.assert_allclose(ghi.values, (dni*cosz).values + dhi.values, rtol=0.05, atol=20.0)
    assert (dni >= 0).all()
    assert (dhi >= 0).all()



def test_global_fraction_direct_is_dni(monkeypatch):
    idx = pd.date_range("2024-06-21 18:00", periods=2, freq="1h", tz="UTC")
    ghi = pd.Series([800.0, 600.0], index=idx, name="global_shortwave")
    zen = pd.Series([30.0, 60.0], index=idx, name="zenith")  # cos=~0.866, 0.5

    params = {
        "global_shortwave": {"source": "global_src"},
        "zenith": {"source": "pvlib"},
        "direct_shortwave": {"source": "global_80%"},
        "diffuse_shortwave": {"source": "global_20%"},
    }
    dfs = {
        "global_src": pd.DataFrame({"global_shortwave": ghi}, index=idx),
        "pvlib": pd.DataFrame({"zenith": zen}, index=idx),
    }
    out = process_global_data(params, idx, dfs, latitude=35.0, longitude=-106.6, elevation=1600.0)
    dni = out["direct_shortwave"];  dhi = out["diffuse_shortwave"]

    # Expect: BHI = 0.8*GHI -> DNI = BHI/cosz
    exp_dni = (0.8 * ghi / np.cos(np.radians(zen))).clip(lower=0.0)
    exp_dhi = (ghi - 0.8 * ghi).clip(lower=0.0)
    np.testing.assert_allclose(dni.values, exp_dni.values, rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(dhi.values, exp_dhi.values, rtol=1e-6, atol=1e-6)

