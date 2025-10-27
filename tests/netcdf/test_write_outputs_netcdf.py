"""
Ensure write_outputs can write NetCDF without invoking legacy writer:
- We pass output_format='netcdf' so it won't touch .met formatting.
- Check file exists and selected global attrs landed.
"""

from pathlib import Path
import pandas as pd
import xarray as xr

from metforce.output import write_outputs

def test_write_outputs_netcdf_only(tmp_path: Path):
    # tiny frame: two timestamps at 1H
    idx = pd.date_range("2024-01-01 00:00", periods=2, freq="1h", tz="UTC")
    df = pd.DataFrame(index=idx)

    nc_path = tmp_path / "out.nc"
    meta = {
        "title": "Outputs router test",
        "institution": "Unit Tests",
        "latitude": 10.0,
        "longitude": 20.0,
        "elevation_m": 123.0,
    }

    write_outputs(
        df,
        outfile_met=None,
        outfile_nc=nc_path,
        output_format="netcdf",
        netcdf_meta=meta,
        header=None,          # ignored in netcdf-only mode
        parameters=None,      # ignored in netcdf-only mode
    )

    assert nc_path.exists()
    ds = xr.open_dataset(nc_path)
    try:
        assert ds.attrs["title"] == "Outputs router test"
        assert float(ds.attrs["geospatial_latitude"]) == 10.0
        assert float(ds.attrs["geospatial_longitude"]) == 20.0
    finally:
        ds.close()
