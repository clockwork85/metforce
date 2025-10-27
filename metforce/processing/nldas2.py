from __future__ import annotations

import datetime
from pathlib import Path
import shutil
from typing import Dict, List, Optional, Union, Any

import numpy as np
import pandas as pd
import xarray as xr
import earthaccess as ea

from metforce.logger_config import logger
from metforce.processing.util import check_for_missing_dates
from metforce.data_types import Parameters  # or define your own type alias
from metforce.physics.wind import resample_wind_vector_mean

###############################################################################
# 0) Earthaccess login helper
###############################################################################
def _earthaccess_login() -> None:
    """
    Perform NASA Earthdata/Earthaccess login if not already authenticated.
    Raises an exception if credentials are invalid.
    """
    try:
        ea.login()  # caches a token if possible
    except Exception as exc:
        logger.error(f"Earthaccess login failed: {exc}")
        raise


###############################################################################
# 1) Decide which dates to fetch, just like get_grib_dates
###############################################################################
def get_nldas2_dates(
    metdata: pd.DataFrame | None,
    parameters: Dict[str, Dict[str, Any]],
    date_range: pd.DatetimeIndex,
    interp_method: Union[str, bool, None],
    pull_nldas2: bool
) -> List[datetime.datetime]:
    """
    Determine which timestamps actually need to be pulled from NLDAS2.
    Mirrors the logic in get_grib_dates.
    """
    logger.debug(f"From get_nldas2_dates: {parameters=}")

    # Do we have *any* parameters that come from NLDAS2?
    any_nldas = any(
        param_info.get("source") == "nldas2"
        for param_info in parameters.values()
    )
    # If none are from NLDAS2 or the user disabled pulling, skip
    if not any_nldas or not pull_nldas2:
        return []

    # If there's no station data, or we explicitly want NLDAS2
    if metdata is None:
        return list(date_range.to_pydatetime())

    # If station data is provided but no interpolation method, fill missing from NLDAS2
    if interp_method is None and pull_nldas2:
        return check_for_missing_dates(metdata, date_range)

    # Otherwise, we have station data plus an interpolation method,
    # but we still have NLDAS2-based parameters => we pull entire range
    return list(date_range.to_pydatetime())


###############################################################################
# 2) NLDAS2 "getter" functions (same info as GRIB-based approach)
###############################################################################
def subselect_point(ds: xr.Dataset, lat: float, lon: float) -> xr.Dataset:
    """
    Return ds reduced to the nearest lat/lon point.
    """
    return ds.sel(lat=lat, lon=lon, method="nearest")

def get_pressure_nldas2(ds: xr.Dataset, lat: float, lon: float) -> float:
    """
    Pressure in Pa → kPa. NetCDF var 'PSurf'.
    """
    point = subselect_point(ds, lat, lon)
    p_pa = float(point["PSurf"].values)
    return p_pa / 1000.0  # kPa

def get_temperature_nldas2(ds: xr.Dataset, lat: float, lon: float) -> float:
    """
    Tair in K → Celsius. NetCDF var 'Tair'.
    """
    point = subselect_point(ds, lat, lon)
    t_k = float(point["Tair"].values)
    return t_k - 273.15

def get_relative_humidity_nldas2(ds: xr.Dataset, lat: float, lon: float) -> float:
    """
    Convert Qair (kg/kg) to RH%. Also need Tair (K) & PSurf (Pa).
    """
    point = subselect_point(ds, lat, lon)
    qair = float(point["Qair"].values)
    p_pa = float(point["PSurf"].values)
    t_k  = float(point["Tair"].values)

    # T in Celsius for the saturation vapor pressure calculation
    t_c = t_k - 273.15
    es = 6.112 * np.exp(17.67 * t_c / (t_c + 243.5)) * 100.0  # Pa
    e = qair * p_pa / (0.622 + 0.378 * qair)
    rh = e / es * 100.0
    return rh

def get_zonal_wind_nldas2(ds: xr.Dataset, lat: float, lon: float) -> float:
    """
    Eastward wind (m/s), typically 10m. NetCDF var 'Wind_E'.
    """
    point = subselect_point(ds, lat, lon)
    return float(point["Wind_E"].values)

def get_meridional_wind_nldas2(ds: xr.Dataset, lat: float, lon: float) -> float:
    """
    Northward wind (m/s). NetCDF var 'Wind_N'.
    """
    point = subselect_point(ds, lat, lon)
    return float(point["Wind_N"].values)

def get_wind_speed_nldas2(ds: xr.Dataset, lat: float, lon: float, surface_roughness: float = 0.34) -> float:
    """
    Combine east & north wind, then log-scale from 10m → 2m
    """
    ue = get_zonal_wind_nldas2(ds, lat, lon)
    vn = get_meridional_wind_nldas2(ds, lat, lon)
    wind_10m = np.sqrt(ue**2 + vn**2)
    # 10m → 2m
    return wind_10m * np.log(2.0 / surface_roughness) / np.log(10.0 / surface_roughness)

def get_wind_direction_nldas2(ds: xr.Dataset, lat: float, lon: float) -> float:
    """
    Same direction logic as in grib code.
    """
    ue = get_zonal_wind_nldas2(ds, lat, lon)
    vn = get_meridional_wind_nldas2(ds, lat, lon)

    if ue == 0 and vn == 0:
        return 0.0
    import math
    if ue != 0:
        wd = np.degrees(math.atan2(ue, vn))
    else:
        wd = np.degrees(math.pi/2.0*(vn/abs(vn)))

    if wd < 0:
        wd += 360.0
    return wd

def get_shortwave_radiation_nldas2(ds: xr.Dataset, lat: float, lon: float) -> float:
    """
    'SWdown' (W/m^2).
    """
    point = subselect_point(ds, lat, lon)
    val = float(point["SWdown"].values)
    return max(val, 0.0)

def get_longwave_radiation_nldas2(ds: xr.Dataset, lat: float, lon: float) -> float:
    """
    'LWdown' (W/m^2).
    """
    point = subselect_point(ds, lat, lon)
    return float(point["LWdown"].values)

def get_precipitation_nldas2(ds: xr.Dataset, lat: float, lon: float) -> float:
    """
    'Rainf' (kg/m^2/s). Multiply by 3600 if you want mm/hr.
    For consistency with grib, maybe we just store as "mm/hour" = val*3600.
    Or keep it as "mm" for that hour. It's up to you.
    """
    point = subselect_point(ds, lat, lon)
    val = float(point["Rainf"].values) # mm / hour 
    
    return val  #  No longer need this with NetCDF * 3600.0

###############################################################################
# 3) map your parameter names to the above "getter" functions
###############################################################################
nldas2_function_mapper = {
    "pressure": get_pressure_nldas2,
    "temperature": get_temperature_nldas2,
    "relative_humidity": get_relative_humidity_nldas2,
    "precipitation": get_precipitation_nldas2,
    "wind_speed": get_wind_speed_nldas2,
    "wind_direction": get_wind_direction_nldas2,
    "global_shortwave": get_shortwave_radiation_nldas2,
    "downwelling_lwir": get_longwave_radiation_nldas2,
}


###############################################################################
# 4) Actually search & download each file, parse filenames into dict[datetime] = file
###############################################################################
def pull_nldas2_files(
    nldas2_dates: List[datetime.datetime],
    tmp_data_folder: str,
    cleanup_folder: bool = False,
    **ea_search_kwargs: Any,
) -> Dict[datetime.datetime, str]:
    """
    1. Convert nldas2_dates to [start, end].
    2. Earthaccess search_data(...).
    3. download(...) to tmp_data_folder.
    4. parse each local file name -> datetime.
    5. build dictionary of {timestamp: file_path}.
    """
    results: Dict[datetime.datetime, str] = {}
    if not nldas2_dates:
        logger.debug("No NLDAS2 dates requested, returning empty.")
        return results

    # Step 1: Range
    start = min(nldas2_dates)
    end = max(nldas2_dates)

    # Step 2: Earthaccess search
    _earthaccess_login()
    logger.debug(f"Searching NLDAS2 from {start} to {end} with {ea_search_kwargs=}")

    # Because NLDAS is hourly, we can pass the entire [start, end].
    granules = ea.search_data(
        short_name="NLDAS_FORA0125_H",
        version="2.0",
        temporal=(start, end),
        **ea_search_kwargs
    )
    logger.debug(f"Found {len(granules)} NLDAS2 granules to download.")

    # Step 3: Download
    tmp_path = Path(tmp_data_folder).expanduser()
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        local_files = ea.download(granules, str(tmp_path))
    except Exception as e: 
        logger.error(f"Failed to download {granules} to {str(tmp_path)}")
        logger.exception(e)
    logger.debug(f"Downloaded {len(local_files)} files to {tmp_path}")

    # Step 4: parse each file name -> datetime
    for fpath in local_files:
        fn = Path(fpath).name
        # Example: NLDAS_FORA0125_H.A20250101.0000.020.nc
        try:
            parts = fn.split(".")  # e.g. ["NLDAS_FORA0125_H", "A20250101", "0000", "020", "nc"]
            date_str = parts[1]  # "A20250101"
            time_str = parts[2]  # "0000"

            # Chop leading 'A' from date_str
            date_str = date_str[1:]  # => "20250101"
            yyyy = int(date_str[0:4])
            mm = int(date_str[4:6])
            dd = int(date_str[6:8])
            HH = int(time_str[0:2])  # "00"
            MN = int(time_str[2:4])  # "00"
            file_dt = datetime.datetime(yyyy, mm, dd, HH, MN)

            # We only store it if it's in nldas2_dates
            if file_dt in nldas2_dates:
                results[file_dt] = str(Path(fpath).absolute())
        except Exception as e:
            logger.warning(f"Could not parse date/time from {fn}: {e}")

    # Step 5: Optionally cleanup
    if cleanup_folder:
        logger.debug(f"Removing temporary folder {tmp_path}")
        shutil.rmtree(tmp_path, ignore_errors=True)

    logger.debug(f"NLDAS2: matched {len(results)}/{len(nldas2_dates)} requested hours.")
    return results


###############################################################################
# 5) Build the final DataFrame from date->file just like build_grib_df
###############################################################################
def build_nldas2_df(
    parameters: list[str],
    files_or_dict: list[str] | dict[datetime.datetime, str],
    latitude: float,
    longitude: float,
) -> pd.DataFrame:
    """
    Builds a DataFrame of NLDAS2 (or similar netCDF) data for the given parameters.

    If `files_or_dict` is a dict[datetime->file], we assume each file is one time step.
    If `files_or_dict` is a list of filepaths, we assume each file may have multiple times,
    so we do a single combined xarray open and read the entire time dimension.
    """

    # If user passed a dictionary, do the “one-file-per-datetime” logic:
    if isinstance(files_or_dict, dict):
        logger.debug("Building NLDAS2 DataFrame from date->file dictionary.")
        nldas2_dates = sorted(files_or_dict.keys())
        if not nldas2_dates:
            return pd.DataFrame()  # nothing
        # Build up columns by reading each file once per param
        param_data: dict[str, list[float]] = {p: [] for p in parameters}
        for dt in nldas2_dates:
            fpath = files_or_dict[dt]
            ds = xr.open_dataset(fpath, engine="netcdf4")
            ds_time = ds.sel(time=dt, method="nearest")
            for p in parameters:
                if p not in nldas2_function_mapper:
                    raise NotImplementedError(
                        f"Parameter '{p}' not in nldas2_function_mapper. "
                        f"Known keys: {list(nldas2_function_mapper.keys())}"
                    )
                val = nldas2_function_mapper[p](ds_time, latitude, longitude)
                param_data[p].append(val)

        # Convert each param’s list -> Series
        param_series = {
            p: pd.Series(vals, index=nldas2_dates) for p, vals in param_data.items()
        }
        df = pd.DataFrame(param_series)
        return df

    # If user passed a list of file paths, open them all in one multi-file dataset:
    else:
        logger.debug("Building NLDAS2 DataFrame from a list of multi-time netCDF files.")
        ds = xr.open_mfdataset(files_or_dict, combine="by_coords")
        # We expect a time dimension for multiple steps:
        if "time" not in ds.coords:
            # If there's no time dimension, we can treat it as a single snapshot
            # or just raise an error. Let's raise:
            raise ValueError("NetCDF file(s) do not contain a 'time' coordinate.")

        # For each param, read the entire time dimension and subselect lat/lon
        param_series = {}
        times = ds["time"].values
        for p in parameters:
            if p not in ds.variables:
                raise KeyError(f"Parameter '{p}' is not in the dataset variables: {list(ds.variables)}")
            # subselect the nearest lat/lon for that param
            point_data = ds[p].sel(lat=latitude, lon=longitude, method="nearest")
            # Convert to a 1-D numpy array. If xarray shape is (time,), fine. If (time, lat, lon), it’s size 1 in lat/lon.
            data_array = point_data.values

            # data_array should have one value per time step
            param_series[p] = pd.Series(data_array, index=times)

        df = pd.DataFrame(param_series)

        # If your old code or tests rely on a standard DateTimeIndex, do:
        if np.issubdtype(df.index.dtype, np.datetime64):
            df.index = pd.to_datetime(df.index)

        return df



###############################################################################
# 6) Main entry point: process_nldas2_data, analogous to process_grib_data
###############################################################################
def process_nldas2_data(
    parameters: Parameters,
    metdata: pd.DataFrame | None,
    date_range: pd.DatetimeIndex,
    latitude: float,
    longitude: float,
    tmp_data_folder: str,
    pull_nldas2: bool,
    cleanup_folder: bool,
    interp_method: Optional[str] = None,
    wind_avg_method: str = "legacy_scalar",
    calm_threshold_mps: float = 0.2,
    **ea_search_kwargs: Any,
) -> Optional[pd.DataFrame]:
    """
    Orchestrator that:
      1. Identifies which parameters come from "nldas2"
      2. Figures out which dates we need (get_nldas2_dates)
      3. Pulls the netCDF files via Earthaccess (pull_nldas2_files)
      4. Builds a DataFrame with build_nldas2_df
      5. Returns that DF or None if not applicable

    Additional earthaccess search options can be passed in via **ea_search_kwargs.
    """
    # Which parameters come from nldas2?
    logger.debug(f"In process nldas2: {parameters=}")
    nldas2_params = [
        p for p, meta in parameters.items()
        if meta.get("source") == "nldas2"
    ]
    if not pull_nldas2 and not nldas2_params:
        return None

    # Determine needed dates
    nldas2_dates = get_nldas2_dates(metdata, parameters, date_range, interp_method, pull_nldas2)
    if not nldas2_dates or not nldas2_params:
        logger.debug("No nldas2 parameters or no dates needed - returning None.")
        return None

    # Pull the files (one file per hour)
    nldas2_files_dict = pull_nldas2_files(
        nldas2_dates,
        tmp_data_folder,
        cleanup_folder=cleanup_folder,
        **ea_search_kwargs
    )
    if not nldas2_files_dict:
        logger.warning("No NLDAS2 files returned by earthaccess!")
        return None

    # Build final DF
    nldas2_df = build_nldas2_df(nldas2_params, nldas2_files_dict, latitude, longitude)
    if nldas2_df.empty:
        logger.warning("NLDAS2 DataFrame is empty after build.")
        return None

    # Phase 1.5: if needed, coarsen to the desired cadence.
    # (No effect when source cadence == target cadence.)
    try:
        nldas2_df = _coarsen_nldas2_df_to_date_range(
            nldas2_df, date_range, nldas2_params,
            wind_avg_method=wind_avg_method,
            calm_threshold_mps=calm_threshold_mps,
        )
    except Exception as exc:
        logger.debug(f"Skipping NLDAS coarsening due to {exc!r}")

    return nldas2_df

def _coarsen_nldas2_df_to_date_range(
    df: pd.DataFrame,
    date_range: pd.DatetimeIndex,
    parameters: list[str],
    *,
    wind_avg_method: str = "legacy_scalar",
    calm_threshold_mps: float = 0.2,
) -> pd.DataFrame:
    """
    Coarsen an hourly (or finer) NLDAS2 dataframe to the cadence of `date_range`,
    using vector-mean for wind if wind_avg_method='vector', mean for most scalars,
    and sum for precipitation. Index is aligned to `date_range`.

    If wind_avg_method='legacy_scalar' or the source cadence matches target cadence,
    returns `df.reindex(date_range)` with no aggregation.
    """
    # If target freq equals source, just align index
    src_freq = pd.infer_freq(df.index)
    tgt_freq = date_range.freqstr if date_range.freq is not None else None
    if src_freq == tgt_freq or tgt_freq is None:
        return df.reindex(date_range)

    # Aggregation for non-wind columns
    agg_map: dict[str, str] = {}
    for p in parameters:
        if p == "precipitation" and p in df.columns:
            agg_map[p] = "sum"
        elif p not in ("wind_speed", "wind_direction") and p in df.columns:
            agg_map[p] = "mean"

    # Start with non-wind
    out = pd.DataFrame(index=date_range)
    if agg_map:
        coarsened = df[agg_map.keys()].resample(date_range.freq).aggregate(agg_map)
        out.loc[:, coarsened.columns] = coarsened.reindex(date_range)

    # Then wind
    has_wind = ("wind_speed" in df.columns) and ("wind_direction" in df.columns)
    if has_wind:
        if wind_avg_method == "vector":
            spd_vec, dir_vec = resample_wind_vector_mean(
                df["wind_speed"], df["wind_direction"], date_range,
                calm_threshold_mps=calm_threshold_mps,
            )
            out["wind_speed"] = spd_vec
            out["wind_direction"] = dir_vec
        else:
            # legacy: scalar means (kept for completeness; typically we wouldn't coarsen in legacy mode)
            out["wind_speed"] = df["wind_speed"].resample(date_range.freq).mean().reindex(date_range)
            out["wind_direction"] = df["wind_direction"].resample(date_range.freq).mean().reindex(date_range)

    return out
