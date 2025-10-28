from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping

import numpy as np
import pandas as pd
from pandas.tseries.frequencies import to_offset
import xarray as xr

from metforce.defaults import default_met_units, default_met_width, default_met_decimal, default_col_names
from metforce.logger_config import logger

Parameters = Dict[str, Dict[str, Any]]

# --- QC provenance map ----------------------------------------------------------
_QC_CODE_BY_SOURCE = {
    "met": 1,
    "nldas2": 4,
    "grib": 4,
    "pvlib": 3,
    "global_fraction": 3,
    "global_coszenith": 3,
}
_QC_DEFAULT = 7
_QC_MISSING = 9

# --- Param -> CF var name map (only those we export today) ----------------------
_PARAM_TO_CF = {
    "pressure": "air_pressure",
    "temperature": "air_temperature",
    "relative_humidity": "relative_humidity",
    "wind_speed": "wind_speed",
    "wind_direction": "wind_from_direction",
    "precipitation": "precipitation_amount",
    "global_shortwave": "surface_downwelling_shortwave_flux_in_air",
    "direct_shortwave": "surface_direct_downwelling_shortwave_flux_in_air",
    "diffuse_shortwave": "surface_diffuse_downwelling_shortwave_flux_in_air",
    "downwelling_lwir": "surface_downwelling_longwave_flux_in_air",
    # note: zenith/azimuth not yet written as CF vars in this slice
}

# --- Core coverage set (only variables that exist in the dataset are counted) ---
_CORE_VARS = [
    "air_pressure",
    "air_temperature",
    "relative_humidity",
    "wind_speed",
    "wind_from_direction",
    "precipitation_amount",
    "surface_downwelling_shortwave_flux_in_air",
    "surface_downwelling_longwave_flux_in_air",
]
_COVERAGE_THRESHOLD = 0.80

def build_netcdf_dataset(
        met_df: pd.DataFrame,
        meta: Mapping[str, Any] | None = None,
        *,
        parameters: Mapping[str, Mapping[str, Any]] | None = None,
) -> xr.Dataset:
    """
    Build a minimal xarray
    """
    if not isinstance(met_df.index, pd.DatetimeIndex):
        raise TypeError("met_df must be indexed by a pandas.DatetimeIndex")

    # Normalize to UTC and drop timezone, so CF writers don't choke
    idx = met_df.index
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    # Guarantee monotonic and unique times (common expectation for CF)
    if not idx.is_monotonic_increasing:
        idx = idx.sort_values()

    time = pd.DatetimeIndex(idx, tz=None)

    # ------- Coordinates -----------------
    ds = xr.Dataset(coords={
        "time": ("time", time.values),
        "nv": ("nv", np.array([0, 1], dtype=int)),
    })
    ds["time"].attrs.update({
        "standard_name": "time",
        "long_name": "time of measurement",
        "axis": "T",
        "bounds": "time_bnds",  # CF link to bounds variable
    })
    # ---------- Time bounds --------------
    # Determine interval step robustly without pandas.infer_freq (needs >=3 dates).
    if getattr(time, "freq", None) is not None:
        step = to_offset(time.freq)
    elif len(time) >= 2:
        # use the median step from first differences (works for 2+ samples)
        diffs = pd.Series(time).diff().dropna()
        step = diffs.median()
    else:
        raise ValueError("Cannot infer time bounds from a single timestamp.")

    # End bound is [start, start+step)
    start_bounds = time
    end_bounds = time + step

    tb = np.stack([start_bounds.values, end_bounds.values], axis=1)
    ds["time_bnds"] = xr.DataArray(tb, dims=("time", "nv"))
    ds["time_bnds"].attrs.update(
        {
            "long_name": "start and end of time interval",
            "comment": "Left-closed, right-open bounds: [start, end).",
        }
    )

    ds.attrs.update({
        "Conventions": "CF-1.10",
        "featureType": "timeSeries",
    })

    if meta:
        # Common human metadata
        if meta.get("title") is not None:
            ds.attrs["title"] = meta["title"]
        if meta.get("institution") is not None:
            ds.attrs["institution"] = meta["institution"]
        if meta.get("references") is not None:
            ds.attrs["references"] = meta["references"]

        # Site geospatial summary for easy discovery
        if meta.get("latitude") is not None:
            ds.attrs["geospatial_latitude"] = float(meta["latitude"])
        if meta.get("longitude") is not None:
            ds.attrs["geospatial_longitude"] = float(meta["longitude"])
        if meta.get("elevation_m") is not None:
            elev = float(meta["elevation_m"])
            ds.attrs["geospatial_vertical_min"] = elev
            ds.attrs["geospatial_vertical_max"] = elev
            ds.attrs["geospatial_vertical_units"] = "m"
            ds.attrs["geospatial_vertical_positive"] = "up"

    def _var(name: str, values: np.ndarray, attrs: Mapping[str, Any]) -> None:
        ds[name] = xr.DataArray(values, dims=("time",))
        ds[name].attrs.update(dict(attrs))

    col = met_df.get

    if "Press" in met_df:
        _var(
            "air_pressure",
            col("Press").to_numpy(dtype=float) * 100.0,
            {"standard_name": "air_pressure", "long_name": "air pressure", "units": "Pa", "cell_methods": "time: mean"},
        )

    # Air temperature: Temp (degC) → degC (NetCDF spec later may carry K; here we keep degC as you do today)
    if "Temp" in met_df:
        _var(
            "air_temperature",
            col("Temp").to_numpy(dtype=float),
            {"standard_name": "air_temperature", "long_name": "air temperature", "units": "degC", "cell_methods": "time: mean"},
        )

    # Relative humidity: RH (%) → 0–1
    if "RH" in met_df:
        _var(
            "relative_humidity",
            col("RH").to_numpy(dtype=float) / 100.0,
            {"standard_name": "relative_humidity", "long_name": "relative humidity (fraction)", "units": "1", "cell_methods": "time: mean"},
        )

    # Wind: speed + from-direction (no unit change)
    if "WndSpd" in met_df:
        _var(
            "wind_speed",
            col("WndSpd").to_numpy(dtype=float),
            {"standard_name": "wind_speed", "long_name": "wind speed", "units": "m s-1", "cell_methods": "time: mean"},
        )
    if "WndDir" in met_df:
        _var(
            "wind_from_direction",
            col("WndDir").to_numpy(dtype=float),
            {"standard_name": "wind_from_direction", "long_name": "wind from direction", "units": "degree", "cell_methods": "time: mean"},
        )

    # Precipitation: Precip (mm per interval) → kg m-2 (numerically same for liquid water), time: sum
    if "Precip" in met_df:
        _var(
            "precipitation_amount",
            col("Precip").to_numpy(dtype=float),
            {"standard_name": "precipitation_amount", "long_name": "precipitation amount", "units": "kg m-2", "cell_methods": "time: sum"},
        )

    # Shortwave fluxes (W m-2)
    if "Global" in met_df:
        _var(
            "surface_downwelling_shortwave_flux_in_air",
            col("Global").to_numpy(dtype=float),
            {"standard_name": "surface_downwelling_shortwave_flux_in_air", "long_name": "global shortwave flux", "units": "W m-2", "cell_methods": "time: mean"},
        )
    if "Direct" in met_df:
        _var(
            "surface_direct_downwelling_shortwave_flux_in_air",
            col("Direct").to_numpy(dtype=float),
            {"standard_name": "surface_direct_downwelling_shortwave_flux_in_air", "long_name": "direct shortwave flux", "units": "W m-2", "cell_methods": "time: mean"},
        )
    if "Diffuse" in met_df:
        _var(
            "surface_diffuse_downwelling_shortwave_flux_in_air",
            col("Diffuse").to_numpy(dtype=float),
            {"standard_name": "surface_diffuse_downwelling_shortwave_flux_in_air", "long_name": "diffuse shortwave flux", "units": "W m-2", "cell_methods": "time: mean"},
        )

    # Longwave flux (W m-2)
    if "LWdwn" in met_df:
        _var(
            "surface_downwelling_longwave_flux_in_air",
            col("LWdwn").to_numpy(dtype=float),
            {"standard_name": "surface_downwelling_longwave_flux_in_air", "long_name": "downwelling longwave flux", "units": "W m-2", "cell_methods": "time: mean"},
        )

    # Convenience variables
    iso = pd.to_datetime(time).strftime("%Y-%m-%dT%H:%M:%SZ")
    _var("iso_time", np.array(iso, dtype=object), {"long_name": "timestamp ISO8601 (UTC)"})
    _var("day_of_year", pd.Series(time).dt.dayofyear.to_numpy(),
         {"long_name": "day of year (1..366)", "units": "1"})

    # QC flags (if parameters mapping is supplied)
    if parameters:
        # Build per-CF-var base code from the config sources
        base_code_for_cf: dict[str, int] = {}
        for p_name, p_meta in parameters.items():
            cf = _PARAM_TO_CF.get(p_name)
            if not cf or cf not in ds:
                continue
            src = str(p_meta.get("source", "")).lower()
            base_code_for_cf[cf] = _QC_CODE_BY_SOURCE.get(src, _QC_DEFAULT)

        # Add qc_flag_<var> arrays
        for cf_var, code in base_code_for_cf.items():
            qc = np.full(ds.sizes["time"], code, dtype=np.int8)
            vals = ds[cf_var].values
            if np.issubdtype(vals.dtype, np.floating):
                qc[np.isnan(vals)] = _QC_MISSING
            ds[f"qc_flag_{cf_var}"] = xr.DataArray(qc, dims=("time",))
            ds[f"qc_flag_{cf_var}"].attrs.update({
                "long_name": f"quality flag for {cf_var}",
                "flag_values": [1, 3, 4, 7, 9],
                "flag_meanings": "station derived nldas2 unknown missing",
            })

    # Coverage gate (only count core vars that actually exist)
    present_core = [v for v in _CORE_VARS if v in ds]
    if present_core:
        coverages = []
        for v in present_core:
            arr = ds[v].values
            valid = np.count_nonzero(~np.isnan(arr)) if np.issubdtype(arr.dtype, np.floating) else arr.size
            frac = float(valid) / float(arr.size)
            coverages.append(frac)
        min_frac = float(min(coverages)) if coverages else 1.0
        ds.attrs["coverage_min_fraction_core"] = min_frac
        ds.attrs["coverage_ok"] = int(min_frac >= _COVERAGE_THRESHOLD)

    return ds


def write_netcdf(ds: xr.Dataset, path: Path, *, engine: str | None = None) -> None:
    """
    Serialize Dataset to NetCDF. Final encodings (compression/chunking) later
    """
    engine = engine or "netcdf4"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure CF-style time encodings so bounds + time share the same units
    units = "seconds since 1970-01-01 00:00:00"
    cal = "standard"
    if "time" in ds:
        enc = dict(ds["time"].encoding or {})
        enc.setdefault("units", units)
        enc.setdefault("calendar", cal)
        ds["time"].encoding = enc
    if "time_bnds" in ds:
        encb = dict(ds["time_bnds"].encoding or {})
        encb.setdefault("units", units)
        encb.setdefault("calendar", cal)
        ds["time_bnds"].encoding = encb

    logger.info(f"Writing NetCDF to {path}")
    ds.to_netcdf(path, engine=engine)


def write_outputs(
    met_df: pd.DataFrame,
    *,
    outfile_met: Path | None,
    outfile_nc: Path | None,
    output_format: str = "met",
    netcdf_meta: Mapping[str, Any] | None = None,
    header: str | None = None,
    parameters: Parameters | None = None,
) -> None:
    """
    Unified writer: writes legacy .met, NetCDF, or both.
    - Legacy .met requires header and parameters.
    - NetCDF uses the Dataset builder + meta.
    """
    wrote = False

    if output_format in {"met", "both"} and outfile_met is not None:
        if header is None or parameters is None:
            raise ValueError("write_outputs: header and parameters are required for legacy '.met' output")
        write_met_data(met_df, str(outfile_met), header, parameters)
        wrote = True

    if output_format in {"netcdf", "both"} and outfile_nc is not None:
        ds = build_netcdf_dataset(met_df, meta=netcdf_meta or {})
        write_netcdf(ds, outfile_nc)
        wrote = True

    if not wrote:
        logger.warning("write_outputs: nothing written (check output_format and file paths)")


def create_header(location_name: str, latitude: float, longitude: float, elevation: float, start_range: str, end_range: str, freq: str) -> str:
    if location_name is None:
        location_name = "Location"

    # Parse the start_range string using the provided format to get the year
    start_date = datetime.strptime(start_range, "%Y-%m-%d %H:%M")
    year = start_date.year

    header = f"{location_name} Met Data from {start_range} to {end_range} at {freq} resolution\n"
    header += f"Elevation(m) Latitude Longitude GMT-UTC Year\n"
    header += f"{elevation} {latitude} {longitude} 0 {year}\n"
    return header


def write_met_data(met_df: pd.DataFrame, outfile: str, header: str, parameters: Parameters, write_source: bool = False) -> None:
    """
    Writes the met data to the output file.

    Parameters
    ----------
    met_df : pd.DataFrame
        The DataFrame containing the met data.
    outfile : str
        The output file path.
    header : str
        The header string to be written in the output file.
    parameters : Parameters
        Various parameters.

    Returns
    -------
    None
    """

    logger.info(f"Writing met data to {outfile}")
    max_lengths = {}
    # Finding the maximum lengths for each column
    for col in met_df.columns:
        decimals = default_met_decimal.get(col, 0) # default to zero decimal places
        max_length = max(len(f'{item:.{decimals}f}') if isinstance(item, float) else len(str(item)) for item in met_df[col]) + 1
        # Compare with default width and take the larger value
        max_lengths[col] = max(max_length, default_met_width[col])

    units = [default_met_units.get(col) for col in met_df.columns]
    with open(outfile, 'w') as f:
        f.write(header)
        for col in met_df.columns:
            f.write(f'{default_col_names[col]:<{max_lengths[col]}}')
        f.write('\n')

        for col, unit in zip(met_df.columns, units):
            f.write(f'{unit:<{max_lengths[col]}}')
        f.write('\n')

        # Write the sources
        if write_source:
            for col in met_df.columns:
                if col == 'day':
                    f.write('# Sources - ')
                elif col == 'hour' or col == 'minute':
                    continue
                else:
                    source = parameters.get(col, {}).get('source', '-')
                    f.write(f"{source:<{max_lengths[col]}}")
            f.write('\n')

        for index, row in met_df.iterrows():
            for col, item in zip(met_df.columns, row):
                decimals = default_met_decimal.get(col, 0)
                logger.trace(f"Writing {item} to {col} with {decimals} decimal places")
                try:
                    formatted_item = f'{item:.{decimals}f}'
                except ValueError:
                    formatted_item = f'{item}'
                f.write(f'{formatted_item:<{max_lengths[col]}}')
            f.write('\n')

