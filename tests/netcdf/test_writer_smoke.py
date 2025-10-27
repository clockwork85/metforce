"""
Smoke test:
- Build a minimal Dataset from a tiny UTC index.
- Ensure 'time'_coord exists and we can write/read a NetCDF file.
"""

from pathlib import Path
import pandas as pd
import xarray as xr

from metforce.output import build_netcdf_dataset, write_netcdf

def test_build_and_write_netcdf(tmp_path: Path):
    idx = pd.date_range("2023-01-01 00:00", periods=3, freq="15min", tz="UTC")
    met_df = pd.DataFrame(index=idx)

    ds = build_netcdf_dataset(met_df, meta={"title": "Smoke test", "institution": "Unit Tests"})
    assert "time" in ds.coords and ds.sizes["time"] == 3

    out = tmp_path / "smoke.nc"
    write_netcdf(ds, out)
    ds2 = xr.open_dataset(out)
    try:
        assert ds2.sizes["time"] == 3
        assert ds2.attrs.get("Conventions") == "CF-1.10"
    finally:
        ds2.close()
