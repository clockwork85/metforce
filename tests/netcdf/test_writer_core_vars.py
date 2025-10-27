"""
Verify legacy->CF mapping and units:
- Press mbar -> air_pressure Pa
- RH % -> 0–1
- Precip mm per interval -> kg m-2 with 'time: sum'
- Wind pass-through naming/units
- SW/LW fluxes mapped with 'time: mean'
"""

import numpy as np
import pandas as pd

from metforce.output import build_netcdf_dataset

def test_core_mapping_and_units():
    idx = pd.date_range("2023-01-01 00:00", periods=2, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "Press":  [1013.4, 1012.0],  # mbar
        "Temp":   [20.0,   21.0],    # degC
        "RH":     [50.0,   40.0],    # %
        "WndSpd": [3.0,    4.0],     # m/s
        "WndDir": [350.0,  20.0],    # degree
        "Precip": [0.5,    1.0],     # mm per hour
        "Global": [300.0,  500.0],   # W m-2
        "Direct": [200.0,  350.0],   # W m-2
        "Diffuse":[100.0,  150.0],   # W m-2
        "LWdwn":  [400.0,  410.0],   # W m-2
    }, index=idx)

    ds = build_netcdf_dataset(df, meta={"title": "core vars"})

    np.testing.assert_allclose(ds["air_pressure"].values, [101340.0, 101200.0])
    assert ds["air_pressure"].attrs["units"] == "Pa"

    np.testing.assert_allclose(ds["relative_humidity"].values, [0.5, 0.4])
    assert ds["relative_humidity"].attrs["units"] == "1"

    np.testing.assert_allclose(ds["precipitation_amount"].values, [0.5, 1.0])
    assert ds["precipitation_amount"].attrs["units"] == "kg m-2"
    assert ds["precipitation_amount"].attrs["cell_methods"] == "time: sum"

    np.testing.assert_allclose(ds["wind_speed"].values, [3.0, 4.0])
    np.testing.assert_allclose(ds["wind_from_direction"].values, [350.0, 20.0])
    assert ds["wind_speed"].attrs["units"] == "m s-1"
    assert ds["wind_from_direction"].attrs["units"] == "degree"

    for var in [
        "surface_downwelling_shortwave_flux_in_air",
        "surface_direct_downwelling_shortwave_flux_in_air",
        "surface_diffuse_downwelling_shortwave_flux_in_air",
        "surface_downwelling_longwave_flux_in_air",
    ]:
        assert var in ds
        assert ds[var].attrs.get("units") == "W m-2"
        assert ds[var].attrs.get("cell_methods") == "time: mean"

