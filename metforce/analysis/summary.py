from __future__ import annotations

import xarray as xr
import pandas as pd


def summarize_dataset(nc_path: str) -> pd.DataFrame:
    """
    Get summary statistics for all variables.

    Args:
        nc_path: Path to NetCDF file

    Returns:
        DataFrame with statistics per variable

    Example:
        >>> from metforce.analysis import summarize_dataset
        >>> summary = summarize_dataset("data.nc")
        >>> print(summary)
    """
    ds = xr.open_dataset(nc_path)

    rows = []
    for var in ds.data_vars:
        if var.startswith("qc_") or var in ["iso_time", "day_of_year", "time_bnds"]:
            continue

        attrs = ds[var].attrs
        values = ds[var].values

        row = {
            "variable": var,
            "long_name": attrs.get("long_name", ""),
            "units": attrs.get("units", ""),
            "source": attrs.get("source", ""),
            "min": float(values.min()),
            "max": float(values.max()),
            "mean": float(values.mean()),
            "std": float(values.std()),
            "missing_count": int((values != values).sum()) if hasattr(values, 'sum') else 0,
        }
        rows.append(row)

    return pd.DataFrame(rows)


def get_provenance(nc_path: str, variable: str) -> dict:
    """
    Extract provenance metadata for a variable.

    Args:
        nc_path: Path to NetCDF file
        variable: CF variable name

    Returns:
        Dictionary of provenance attributes
    """
    ds = xr.open_dataset(nc_path)

    if variable not in ds:
        raise ValueError(f"Variable '{variable}' not found")

    attrs = dict(ds[variable].attrs)

    # Extract provenance-specific attributes
    provenance = {}
    prov_keys = [
        "source", "data_type", "measurement_type", "method",
        "instrument_manufacturer", "instrument_model",
        "serial_number", "installation_height",
        "atmospheric_corrections", "comment", "references"
    ]

    for key in prov_keys:
        if key in attrs:
            provenance[key] = attrs[key]

    return provenance