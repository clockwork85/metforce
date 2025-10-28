import sys
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import xarray as xr

from metforce.output import build_netcdf_dataset, write_netcdf, create_header, write_met_data
from metforce.defaults import default_col_names

# Robust .met parser adapted from the regression harness: skip headers, keep rows
# whose first 3 tokens are Day/Hr/Min and the token count matches expectation.
def _read_met(path: Path, *, expected_cols: list[str]) -> pl.DataFrame:
    ncols = len(expected_cols)
    data_rows: list[list[str]] = []
    started = False

    def is_data_row(tokens: list[str]) -> bool: 
        if len(tokens) != ncols: 
            return False
        try:
            d = int(tokens[0]); h = int(tokens[1]); m = int(tokens[2])
        except ValueError: 
            return False

        return 1 <= d <= 366 and 0 <= h <= 23 and 0 <= m <= 59

    with path.open("r", encoding="utf-8", errors="strict") as f: 
        for raw in f: 
            line = raw.strip()
            if not line or line.lstrip().startswith("#"):
                continue
            tokens = line.split()
            if is_data_row(tokens): 
                data_rows.append(tokens)

    if not data_rows: 
        raise AssertionError(f"No data rows recognized in {path}")

    df = pl.DataFrame(data_rows, orient="row")

    df = df.rename({old: new for old, new in zip(df.columns, expected_cols)})

    # cast types by name
    numeric_cols = [c for c in expected_cols if c not in {"Day", "Hr", "Min"}]
    return df.with_columns(
            pl.col("Day").cast(pl.Int64, strict=False),
            pl.col("Hr").cast(pl.Int64, strict=False),
            pl.col("Min").cast(pl.Int64, strict=False),
            *[pl.col(c).cast(pl.Float64, strict=False) for c in numeric_cols],
    )


def test_nc_to_met_roundtrip(tmp_path: Path):
    # -- Step 1: build a tiny "legacy-shaped" frame and NetCDF
    idx = pd.date_range("2023-01-01 00:00", periods=3, freq="1h", tz="UTC")
    legacy_df = pd.DataFrame({
        "Press":  [1013.4, 1012.0, 1011.5],  # mbar
        "Temp":   [20.0,   21.0,   22.0],    # degC
        "RH":     [50.0,   40.0,   60.0],    # %
        "WndSpd": [3.0,    4.0,    2.0],     # m/s
        "WndDir": [350.0,  20.0,   10.0],    # deg
        "Precip": [0.5,    0.0,    1.0],     # mm over interval
        "Global": [300.0,  500.0,  0.0],
        "Direct": [200.0,  350.0,  0.0],
        "Diffuse":[100.0,  150.0,  0.0],
        "LWdwn":  [400.0,  410.0,  420.0],
    }, index=idx)

    meta = {"title": "Roundtrip Site", "latitude": 10.0, "longitude": 20.0, "elevation_m": 123.0}
    ds = build_netcdf_dataset(legacy_df, meta=meta)
    nc_path = tmp_path / "input.nc"
    write_netcdf(ds, nc_path)

    # -- Step 2: convert NC -> MET using the new script (subprocess keeps it black-box)
    out_met = tmp_path / "converted.met"
    subprocess.run(
        [sys.executable, str(Path("scripts") / "convert_nc_to_met.py"), str(nc_path), "-o", str(out_met)],
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    # -- Step 3: build a baseline MET using the legacy writer from param-named columns
    # Build "internal" frame with parameter names + discrete parts
    internal = pd.DataFrame({
        "pressure": legacy_df["Press"].values,
        "temperature": legacy_df["Temp"].values,
        "relative_humidity": legacy_df["RH"].values,
        "wind_speed": legacy_df["WndSpd"].values,
        "wind_direction": legacy_df["WndDir"].values,
        "precipitation": legacy_df["Precip"].values,
        "global_shortwave": legacy_df["Global"].values,
        "direct_shortwave": legacy_df["Direct"].values,
        "diffuse_shortwave": legacy_df["Diffuse"].values,
        "downwelling_lwir": legacy_df["LWdwn"].values,
    }, index=idx)
    internal["day"] = idx.dayofyear
    internal["hour"] = idx.hour
    internal["minute"] = idx.minute
    order = [k for k in default_col_names.keys() if k in internal.columns]
    met_df = internal[order]

    header = create_header("Roundtrip Site", 10.0, 20.0, 123.0,
                           idx[0].strftime("%Y-%m-%d %H:%M"),
                           idx[-1].strftime("%Y-%m-%d %H:%M"),
                           "1h")
    baseline_met = tmp_path / "baseline.met"
    write_met_data(met_df, str(baseline_met), header, parameters={})

    # -- Step 4: parse and compare numeric tables (ignore header text formatting)
    # Build the expected column labels as they appear in .met files
    expected_cols = [default_col_names[c] for c in order]
    got = _read_met(out_met, expected_cols=expected_cols)
    exp = _read_met(baseline_met, expected_cols=expected_cols)

    assert got.shape == exp.shape
    # Check discrete day/hr/min exactly
    for col in ["Day", "Hr", "Min"]:
        assert (got[col] == exp[col]).all(), f"Mismatch in discrete column {col}"
    # Float columns within tight tolerances
    float_cols = [c for c in expected_cols if c not in {"Day", "Hr", "Min"}]
    for col in float_cols:
        g, e = got[col].to_numpy(), exp[col].to_numpy()
        assert np.allclose(g, e, rtol=5e-6, atol=5e-4, equal_nan=True), f"{col} mismatch"

