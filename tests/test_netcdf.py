from __future__ import annotations
"""Tests for the NetCDF backend.

We keep two categories:

* **Fast, synthetic tests** – run unconditionally, never touch the
  network.  They work with either a *pandas* **or** *polars* DataFrame
  returned by the library.
* **Optional live tests** – contact NASA/DAAC via *earthaccess* to pull a
  real NLDAS granule.  They only run when the environment variable
  ``NETCDF_LIVE=1`` is set.
"""
from pathlib import Path
from typing import Any
import os

import numpy as np
import pandas as pd
import pytest
import xarray as xr

import metforce.processing.nldas2 as nldas2 

try:  # polars is an optional dependency downstream
    import polars as pl  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – CI always has polars
    pl = None  # type: ignore

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _to_pandas(df: Any) -> pd.DataFrame:
    """Return *df* as a pandas DataFrame regardless of backend."""
    if isinstance(df, pd.DataFrame):
        return df
    if pl and isinstance(df, pl.DataFrame):  # type: ignore[arg-type]
        return df.to_pandas()  # pyright: ignore[reportGeneralTypeIssues]
    raise TypeError(f"Unsupported DataFrame type: {type(df)}")


# -----------------------------------------------------------------------------
# Optional live tests – skipped unless opted‑in
# -----------------------------------------------------------------------------

pytestmark_live = pytest.mark.skipif(
    os.getenv("NETCDF_LIVE") != "1",
    reason="Set NETCDF_LIVE=1 to run live Earthaccess NetCDF tests",
)

def _to_pandas(df: Any) -> pd.DataFrame:
    """Return *df* as a pandas DataFrame regardless of backend."""
    if isinstance(df, pd.DataFrame):
        return df
    if pl and isinstance(df, pl.DataFrame):  # type: ignore[arg-type]
        return df.to_pandas()  # pyright: ignore[reportGeneralTypeIssues]
    raise TypeError(f"Unsupported DataFrame type: {type(df)}")


# -----------------------------------------------------------------------------
# Fixtures – synthetic data
# -----------------------------------------------------------------------------

@pytestmark_live  # runtime skip unless env‑var is set
@pytest.fixture(scope="module")  # pragma: no cover – live only
def live_netcdf(tmp_path_factory) -> Path:  # type: ignore[override](tmp_path_factory) -> Path:  # type: ignore[override]
    """Download one real NLDAS granule (NetCDF) for live testing.

    Skips automatically if the required NetCDF backend (``netcdf4`` or
    ``h5netcdf``) is **not** installed.  Xarray needs one of these to
    open HDF5‑based NetCDF‑4 files.
    """

    try:
        import netCDF4  # noqa: F401
        _engine_ok = True
    except ModuleNotFoundError:
        try:
            import h5netcdf  # noqa: F401
            _engine_ok = True
        except ModuleNotFoundError:
            _engine_ok = False

    if not _engine_ok:
        pytest.skip("netCDF4 / h5netcdf backend not installed – live test skipped")

    import earthaccess as ea

    ea.login(strategy="netrc")  # raises if credentials missing
    when = pd.Timestamp("2025-01-01 00:00")
    gran = ea.search_data(
        short_name="NLDAS_FORA0125_H",
        version="2.0",
        temporal=(when, when),
    )
    root = tmp_path_factory.mktemp("live_nc")
    files = ea.download(gran, local_path=root)
    if not files:
        pytest.skip("earthaccess returned no granules")
    return Path(files[0])   # type: ignore[override]


@pytestmark_live  # type: ignore[arg-type]
def test_build_netcdf_df_live(live_netcdf: Path):  # pragma: no cover
    ds = xr.open_dataset(live_netcdf)
    pick_vars = [v for v in ["Tair", "PSurf", "Wind_E", "Rainf"] if v in ds.variables][:2]
    if len(pick_vars) < 2:
        print(f"{ds.variables=}")
        pytest.skip("Expected variables not present – dataset schema changed?")

    lat = float(ds.lat.values[0])
    lon = float(ds.lon.values[0])

    df_any = nldas2.build_nldas2_df(pick_vars, [str(live_netcdf)], latitude=lat, longitude=lon)
    pdf = _to_pandas(df_any)

    assert pdf.shape[0] >= 1
    for pv in pick_vars:
        assert pv in pdf.columns

