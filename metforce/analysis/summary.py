from __future__ import annotations

import argparse
from typing import Any

import xarray as xr
import numpy as np
import pandas as pd
import polars as pl

from metforce.logger_config import logger

def summarize_dataset(nc_path: str) -> tuple[pl.DataFrame, dict[str, Any]]:
    """
    Get summary statistics for numeric variables and dataset time coverage.

    Args:
        nc_path: Path to NetCDF file

    Returns:
        A tuple containing:
        1. (stats_df): DataFrame with statistics per numeric variable.
        2. (time_summary): Dictionary with human-readable time coverage.
    """
    ds = xr.open_dataset(nc_path)

    # --- 1. Get Numeric Stats (same as your original code) ---
    rows = []
    for var in ds.data_vars:
        # Skip non-numeric or QC variables
        if var.startswith("qc_") or var in ["iso_time", "day_of_year", "time_bnds"]:
            continue
            
        # Ensure we only process numeric data
        if not np.issubdtype(ds[var].dtype, np.number):
            continue

        attrs = ds[var].attrs
        values = ds[var].values

        row = {
            "variable": var,
            "long_name": attrs.get("long_name", ""),
            "units": attrs.get("units", ""),
            "source": attrs.get("source", ""),
            "min": float(np.nanmin(values)),  # Use nanmin/nanmax
            "max": float(np.nanmax(values)),
            "mean": float(np.nanmean(values)),
            "std": float(np.nanstd(values)),
            "missing_count": int(np.isnan(values).sum()), # More robust for floats
        }
        rows.append(row)

    stats_df = pl.DataFrame(rows)

    # --- 2. Get Time Summary ---
    time_summary = {"status": "No time information found."}
    
    # 'time_bnds' is the most accurate source, as it gives the *true* end time
    if "time_bnds" in ds.data_vars:
        try:
            # Convert to pandas objects for easy formatting
            start_time_pd = pd.to_datetime(ds.time_bnds[0, 0].values)
            end_time_pd = pd.to_datetime(ds.time_bnds[-1, 1].values)
            interval_pd = pd.to_timedelta(ds.time_bnds[0, 1].values - ds.time_bnds[0, 0].values)
            
            # --- Human-Friendly Formatting ---
            interval_minutes = interval_pd.total_seconds() / 60
            
            time_summary = {
                "start_time": start_time_pd.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time_pd.strftime("%Y-%m-%d %H:%M:%S"),
                "interval": f"{interval_minutes:.0f} minutes",
                "n_timesteps": len(ds.time),
                "source": "time_bnds",
            }
        except Exception as e:
            time_summary = {"status": f"Failed to parse 'time_bnds': {e}"}
            
    # Fallback: Use the 'time' coordinate if 'time_bnds' isn't available
    elif "time" in ds.coords:
        try:
            start_time_pd = pd.to_datetime(ds.time[0].values)
            end_time_pd = pd.to_datetime(ds.time[-1].values)
            
            interval_str = "N/A (only one timestep)"
            if len(ds.time) > 1:
                interval_pd = pd.to_timedelta(ds.time[1].values - ds.time[0].values)
                interval_minutes = interval_pd.total_seconds() / 60
                interval_str = f"{interval_minutes:.0f} minutes"

            time_summary = {
                "start_time": start_time_pd.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time_pd.strftime("%Y-%m-%d %H:%M:%S") + " (start of last interval)",
                "interval": interval_str,
                "n_timesteps": len(ds.time),
                "source": "time coordinate",
            }
        except Exception as e:
             time_summary = {"status": f"Failed to parse 'time' coordinate: {e}"}

    return stats_df, time_summary


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

def main() -> None:
    p = argparse.ArgumentParser(description="Summarize MetForce NetCDF file")
    p.add_argument("input_nc", type=str, help="Path to input NetCDF")
    args = p.parse_args()
    summary_out, time_summary = summarize_dataset(args.input_nc)
    #logger.info(out)
    with pl.Config(tbl_rows=-1, tbl_cols=-1): 
        logger.info(summary_out)

    logger.info("\nTemporal Coverage Summary\n"  \
    f"==================================\n"
    f"  Start Time:  {time_summary.get('start_time', 'N/A')}\n" \
    f"  End Time:    {time_summary.get('end_time', 'N/A')}\n" \
    f"  Interval:    {time_summary.get('interval', 'N/A')}\n" \
    f"  Timesteps:   {time_summary.get('n_timesteps', 'N/A')}\n" \
    f"  Source:      {time_summary.get('source', 'N/A')}\n" \
)


if __name__ == "__main__":
    main()

