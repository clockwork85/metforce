from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from pandas.tseries.frequencies import to_offset
import xarray as xr

from metforce.defaults import default_met_units, default_met_width, default_met_decimal, default_col_names
from metforce.logger_config import logger

Parameters = dict[str, dict[str, Any]]

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
    "diffuse_shortwave": "surface_diffuse_downwelling_shortwave_flux_in_air",
    "downwelling_lwir": "surface_downwelling_longwave_flux_in_air",
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


def _normalize_time_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """UTC‑normalize, monotonic, tz‑naive index for CF writing."""
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    if not idx.is_monotonic_increasing:
        idx = idx.sort_values()
    return pd.DatetimeIndex(idx, tz=None)


def _infer_step(time: pd.DatetimeIndex) -> pd.Timedelta | pd.DateOffset:
    """Robust step inference (works with 2+ timestamps)."""
    if getattr(time, "freq", None) is not None:
        return to_offset(time.freq)
    if len(time) >= 2:
        diffs = pd.Series(time).diff().dropna()
        return diffs.median()
    raise ValueError("Cannot infer time bounds from a single timestamp.")




def build_netcdf_dataset(
    met_df: pd.DataFrame,
    meta: Mapping[str, Any] | None = None,
    *,
    parameters: Mapping[str, Mapping[str, Any]] | None = None,
) -> xr.Dataset:
    """
    Build a CF‑1.10-ish *timeSeries* Dataset from a legacy‑shaped or
    param‑named DataFrame. The function accepts both:
      - legacy columns like 'Press', 'Direct', 'Global', ...
      - internal param names like 'pressure', 'direct_shortwave', ...

    Direct irradiance policy:
      * We *always* emit the horizontal direct variable
        'surface_direct_downwelling_shortwave_flux_in_air' (BHI).
      * We also emit 'surface_direct_along_beam_shortwave_flux_in_air' (DNI).
      * If zenith is available, BHI = DNI·cos(zenith).
        Otherwise BHI falls back to the provided direct values (assumed DNI)
        and carries a clarifying comment.
    """
    if not isinstance(met_df.index, pd.DatetimeIndex):
        raise TypeError("met_df must be indexed by a pandas.DatetimeIndex")

    # coords: time, nv ----------------------------------------------------------
    time = _normalize_time_index(met_df.index)
    ds = xr.Dataset(coords={
        "time": ("time", time.values),
        "nv": ("nv", np.array([0, 1], dtype=int)),
    })
    ds["time"].attrs.update({
        "standard_name": "time",
        "long_name": "time of measurement",
        "axis": "T",
        "bounds": "time_bnds",
    })

    # time bounds: [start, start+step)
    step = _infer_step(time)
    tb = np.stack([time.values, (time + step).values], axis=1)
    ds["time_bnds"] = xr.DataArray(tb, dims=("time", "nv"))
    ds["time_bnds"].attrs.update({
        "long_name": "start and end of time interval",
        "comment": "Left-closed, right-open bounds: [start, end).",
    })

    # globals
    ds.attrs.update({"Conventions": "CF-1.10", "featureType": "timeSeries"})
    if meta:
        if meta.get("title") is not None:
            ds.attrs["title"] = meta["title"]
        if meta.get("institution") is not None:
            ds.attrs["institution"] = meta["institution"]
        if meta.get("references") is not None:
            ds.attrs["references"] = meta["references"]
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

    # Accept internal parameter keys OR legacy column labels (from default_col_names)
    def _vals_col(param_key: str, *, dtype=float) -> np.ndarray | None:
        if param_key in met_df.columns:
            return met_df[param_key].to_numpy(dtype=dtype)
        legacy = default_col_names.get(param_key)
        if legacy and legacy in met_df.columns:
            return met_df[legacy].to_numpy(dtype=dtype)
        return None

    def _has_col(param_key: str) -> bool:
        return _vals_col(param_key) is not None

    # --- Core meteorology ------------------------------------------------------
    if _has_col("pressure"):
        _var("air_pressure", _vals_col("pressure") * 100.0,
             {"standard_name": "air_pressure", "long_name": "air pressure",
              "units": "Pa", "cell_methods": "time: mean"})

    if _has_col("temperature"):
        _var("air_temperature", _vals_col("temperature"),
             {"standard_name": "air_temperature", "long_name": "air temperature",
              "units": "degC", "cell_methods": "time: mean"})

    if _has_col("relative_humidity"):
        _var("relative_humidity", _vals_col("relative_humidity") / 100.0,
             {"standard_name": "relative_humidity",
              "long_name": "relative humidity (fraction)",
              "units": "1", "cell_methods": "time: mean"})

    if _has_col("wind_speed"):
        _var("wind_speed", _vals_col("wind_speed"),
             {"standard_name": "wind_speed", "long_name": "wind speed",
              "units": "m s-1", "cell_methods": "time: mean"})

    if _has_col("wind_direction"):
        _var("wind_from_direction", _vals_col("wind_direction"),
             {"standard_name": "wind_from_direction",
              "long_name": "wind from direction",
              "units": "degree", "cell_methods": "time: mean"})

    if _has_col("precipitation"):
        _var("precipitation_amount", _vals_col("precipitation"),
             {"standard_name": "precipitation_amount",
              "long_name": "precipitation amount",
              "units": "kg m-2", "cell_methods": "time: sum"})

    # --- Short-wave & long-wave ------------------------------------------------
    if _has_col("global_shortwave"):
        _var("surface_downwelling_shortwave_flux_in_air", _vals_col("global_shortwave"),
             {"standard_name": "surface_downwelling_shortwave_flux_in_air", "long_name": "global shortwave flux",
              "units": "W m-2", "cell_methods": "time: mean"})

    if _has_col("diffuse_shortwave"):
        _var("surface_diffuse_downwelling_shortwave_flux_in_air", _vals_col("diffuse_shortwave"),
             {"standard_name": "surface_diffuse_downwelling_shortwave_flux_in_air", "long_name": "diffuse shortwave flux",
              "units": "W m-2", "cell_methods": "time: mean"})

    if _has_col("downwelling_lwir"):
        _var("surface_downwelling_longwave_flux_in_air", _vals_col("downwelling_lwir"),
             {"standard_name": "surface_downwelling_longwave_flux_in_air", "long_name": "downwelling longwave flux",
              "units": "W m-2", "cell_methods": "time: mean"})

    # --- Direct short-wave: publish DNI (along-beam) only ---------------------
    if _has_col("direct_shortwave"):
        _var("surface_direct_along_beam_shortwave_flux_in_air", _vals_col("direct_shortwave"),
             {"standard_name": "surface_direct_along_beam_shortwave_flux_in_air",
              "long_name": "direct shortwave flux (DNI, beam-normal)",
              "units": "W m-2", "cell_methods": "time: mean"})

        # Document policy in globals
        ds.attrs["direct_is_dni"] = 1
        ds.attrs["direct_primary_var"] = "surface_direct_along_beam_shortwave_flux_in_air"


    # Optional solar geometry (if present)
    if _has_col("zenith"):
        _var("solar_zenith_angle", _vals_col("zenith"),
             {"standard_name": "solar_zenith_angle", "long_name": "solar zenith angle", "units": "degree", "cell_methods": "time: mean"})

    if _has_col("azimuth"):
        _var("solar_azimuth_angle", _vals_col("azimuth"),
             {"standard_name": "solar_azimuth_angle", "long_name": "solar azimuth angle", "units": "degree", "cell_methods": "time: mean"})



    # --- Optional visibility & aerosol ----------------------------------------
    if _has_col("visibility"):
        vis = _vals_col("visibility")
        if vis is not None:
            vis = np.where(np.asarray(vis, float) < 0.0, np.nan)  # negative sentinel -> NaN
            _var("visibility_in_air", vis,
                 {"standard_name": "visibility_in_air", "long_name": "visibility", "units": "m", "cell_methods": "time: mean"})

    if _has_col("aerosol"):
        aer = _vals_col("aerosol")
        if aer is not None:
            _var("aerosol_legacy", aer,
                 {"long_name": "legacy aerosol indicator from .met",
                  "units": str(default_met_units.get("aerosol", "")),
                  "comment": "Not CF AOD; preserved for provenance."})

    # ---- convenience time variables -------------------------------------------
    iso = pd.DatetimeIndex(time).strftime("%Y-%m-%dT%H:%M:%SZ").to_numpy(dtype=object)
    _var("iso_time", iso, {"long_name": "timestamp ISO8601 (UTC)"})

    _var("day_of_year", pd.Series(time).dt.dayofyear.to_numpy(),
         {"long_name": "day of year (1..366)", "units": "1"})

    # ---- QC flags & coverage ---------------------------------------------------
    if parameters:
        base_code_for_cf: dict[str, int] = {}
        for p_name, p_meta in parameters.items():
            cf = _PARAM_TO_CF.get(p_name)
            if not cf or cf not in ds:
                continue
            src = str(p_meta.get("source", "")).lower()
            base_code_for_cf[cf] = _QC_CODE_BY_SOURCE.get(src, _QC_DEFAULT)

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

    present_core = [v for v in _CORE_VARS if v in ds]
    if present_core:
        fracs = []
        for v in present_core:
            arr = ds[v].values
            valid = np.count_nonzero(~np.isnan(arr)) if np.issubdtype(arr.dtype, np.floating) else arr.size
            fracs.append(float(valid) / float(arr.size))
        min_frac = float(min(fracs)) if fracs else 1.0
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
    netcdf_engine: str | None = None,
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
        idx = pd.DatetimeIndex(met_df['time'].value)
        param_df = met_df.copy()
        param_df['day'] = idx.dayofyear
        param_df['hour'] = idx.hour
        param_df['minute'] = idx.minute
        order = [k for k in default_col_names.keys() if k in param_df.columns]
        final_df = param_df[order]
        write_met_data(final_df, str(outfile_met), header, parameters={})
        wrote = True

    if output_format in {"netcdf", "both"} and outfile_nc is not None:
        ds = build_netcdf_dataset(
            met_df,
            meta=netcdf_meta or {},
            parameters=parameters or {},
        )
        write_netcdf(ds, outfile_nc, engine=netcdf_engine or "netcdf4")
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

