#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import xarray as xr
from pandas.tseries.frequencies import to_offset

from metforce.output import create_header, write_met_data
from metforce.defaults import default_col_names


# CF name -> (internal parameter name used by write_met_data, unit back-converter)
_CF_TO_PARAM: dict[str, tuple[str, callable]] = {
    "air_pressure": ("pressure",        lambda a: np.asarray(a, dtype=float) / 100.0),  # Pa -> mbar
    "air_temperature": ("temperature",  lambda a: np.asarray(a, dtype=float)),          # degC
    "relative_humidity": ("relative_humidity", lambda a: np.asarray(a, dtype=float) * 100.0),  # 0–1 -> %
    "wind_speed": ("wind_speed",        lambda a: np.asarray(a, dtype=float)),          # m s-1
    "wind_from_direction": ("wind_direction", lambda a: np.asarray(a, dtype=float)),    # degree
    "precipitation_amount": ("precipitation", lambda a: np.asarray(a, dtype=float)),    # kg m-2 == mm
    "surface_downwelling_shortwave_flux_in_air": ("global_shortwave",  lambda a: np.asarray(a, dtype=float)),
    "surface_direct_along_beam_shortwave_flux_in_air": ("direct_shortwave",  lambda a: np.asarray(a, dtype=float)),
    "surface_diffuse_downwelling_shortwave_flux_in_air": ("diffuse_shortwave", lambda a: np.asarray(a, dtype=float)),
    "surface_downwelling_longwave_flux_in_air": ("downwelling_lwir",  lambda a: np.asarray(a, dtype=float)),
}


def _to_naive_utc_index(ds: xr.Dataset) -> pd.DatetimeIndex:
    """Return a monotonic, tz‑naive UTC DatetimeIndex."""
    t = ds["time"].to_index()
    if getattr(t, "tz", None) is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    t = pd.DatetimeIndex(t, tz=None)
    if not t.is_monotonic_increasing:
        t = t.sort_values()
    return t


def _infer_freq_str(time: pd.DatetimeIndex) -> str:
    """Robust cadence inference that works with 2 timestamps."""
    if getattr(time, "freq", None) is not None:
        off = to_offset(time.freq)
    elif len(time) >= 2:
        step = pd.Series(time).diff().dropna().median()
        off = to_offset(step)
    else:
        return "unknown"
    return off.freqstr.lower()


def _met_df_from_dataset(ds: xr.Dataset) -> pd.DataFrame:
    """Build the legacy in-memory frame (internal param names + day/hour/minute)."""
    time = _to_naive_utc_index(ds)
    df = pd.DataFrame(index=time)

    # discrete time parts first
    df["day"] = time.dayofyear
    df["hour"] = time.hour
    df["minute"] = time.minute

    # mapped variables from CF names → internal names
    for cf_name, (param, back_convert) in _CF_TO_PARAM.items():
        if cf_name in ds.variables:
            vals = ds[cf_name].values
            df[param] = back_convert(vals)

    # Final column order should match legacy writer expectations
    order = [k for k in default_col_names.keys() if k in df.columns]
    return df[order]


def convert_nc_to_met(in_nc: str | Path, out_met: str | Path | None = None) -> Path:
    """Convert a CF-ish MetForce NetCDF file → legacy `.met` using your existing writer."""
    in_nc = Path(in_nc)
    out_met = Path(out_met) if out_met is not None else in_nc.with_suffix(".met")

    ds = xr.open_dataset(in_nc, engine="netcdf4")

    # Rebuild the legacy frame
    met_df = _met_df_from_dataset(ds)

    # Header: use global attrs your writer already populates when creating NetCDF. :contentReference[oaicite:2]{index=2}
    time = met_df.index
    start = time[0].strftime("%Y-%m-%d %H:%M")
    end   = time[-1].strftime("%Y-%m-%d %H:%M")
    freq  = _infer_freq_str(time)

    location_name = str(ds.attrs.get("title") or "Location")
    lat = float(ds.attrs.get("geospatial_latitude", np.nan))
    lon = float(ds.attrs.get("geospatial_longitude", np.nan))
    elev = float(ds.attrs.get("geospatial_vertical_min",
                       ds.attrs.get("elevation", np.nan)))
    header = create_header(location_name, lat, lon, elev, start, end, freq)

    # Let the existing .met writer handle formatting widths/decimals. :contentReference[oaicite:3]{index=3}
    write_met_data(met_df, str(out_met), header, parameters={}, write_source=False)
    return out_met


def main() -> None:
    p = argparse.ArgumentParser(description="Convert MetForce NetCDF → legacy .met")
    p.add_argument("input_nc", type=str, help="Path to input NetCDF")
    p.add_argument("-o", "--out", type=str, default=None, help="Path for output .met")
    args = p.parse_args()
    out = convert_nc_to_met(args.input_nc, args.out)
    print(out)


if __name__ == "__main__":
    main()

