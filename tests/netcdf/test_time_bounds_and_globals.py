"""
CF-ish behavior for time & metadata:
- 'nv=2', 'time_bnds(time,2)' present
- Bounds correspond to [t, t+Δt)
- Global attrs include Conventions/featureType and geospatial site info when provided
"""

import pandas as pd
import xarray as xr
from pathlib import Path

from metforce.output import build_netcdf_dataset, write_netcdf

def test_time_bounds_and_globals(tmp_path: Path):
    idx = pd.date_range("2023-01-01 00:00", periods=3, freq="30min", tz="UTC")
    df = pd.DataFrame(index=idx)

    ds = build_netcdf_dataset(
        df,
        meta={
            "title": "MetForce time-bounds test",
            "institution": "Unit Tests",
            "latitude": 28.6025,
            "longitude": -81.2001,
            "elevation_m": 28.0,
        },
    )

    assert "time" in ds.coords and "nv" in ds.sizes and ds.sizes["nv"] == 2
    assert ds["time"].attrs.get("bounds") == "time_bnds"
    assert "time_bnds" in ds and ds["time_bnds"].shape == (3, 2)

    t0 = pd.Timestamp("2023-01-01 00:00", tz="UTC").tz_convert(None)
    b0 = pd.to_datetime(ds["time_bnds"].isel(time=0).values)
    assert b0[0] == t0
    assert b0[1] == t0 + pd.Timedelta(minutes=30)

    # global attrs
    assert ds.attrs.get("Conventions") == "CF-1.10"
    assert ds.attrs.get("featureType") == "timeSeries"
    assert float(ds.attrs.get("geospatial_latitude")) == 28.6025
    assert float(ds.attrs.get("geospatial_longitude")) == -81.2001
    assert float(ds.attrs.get("geospatial_vertical_min")) == 28.0
    assert ds.attrs.get("geospatial_vertical_positive") == "up"

    out = tmp_path / "bounds_globals.nc"
    write_netcdf(ds, out)
    assert out.exists()
    ds2 = xr.open_dataset(out)
    try:
        assert ds2["time"].attrs.get("bounds") == "time_bnds"
    finally:
        ds2.close()
