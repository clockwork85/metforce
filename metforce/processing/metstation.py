import datetime
import os
from typing import Dict, List, Optional, Union, Tuple

import numpy as np
import pandas as pd
import pytz

from metforce.data_types import Parameters
from metforce.logger_config import logger


# Function for Met Station data processing
def process_metstation_data(parameters: Parameters, metdata: Optional[pd.DataFrame],
                             date_range: pd.DatetimeIndex, metstation_freq: str, interp_method: Optional[str],
                            elevation: float | None = None) \
        -> Optional[pd.DataFrame]:

    if metdata is None:
        logger.debug("No met station data provided")
        return None

    # Optional: best-effort units sniff from the original Excel header+units rows
    try:
        if os.getenv("MF_UNITS_SNIFF") == "1":
            _mf = os.getenv("METFORCE_METFILE")
            if _mf:
                hdr = (
                    pd.read_excel(_mf, nrows=1, header=None)
                    .iloc[0]
                    .astype(str)
                    .tolist()
                )
                units_row = (
                    pd.read_excel(_mf, nrows=2, header=None)
                    .iloc[1]
                    .astype(str)
                    .tolist()
                )
                col_to_units: dict[str, str] = {}
                for p, k in met_key.items():
                    if k in hdr:
                        j = hdr.index(k)
                        col_to_units[k] = units_row[j] if j < len(units_row) else "?"
                if col_to_units:
                    logger.debug("[units] met columns → {}", col_to_units)
    except Exception as _e:
        logger.debug(
            "[units] best-effort units sniff failed: {}: {}", type(_e).__name__, _e
        )

    met_key = {key: value["key"] for key, value in parameters.items() if value["source"] == "met"}

    if metdata is not None:
        if interp_method is not None:
            metdata = fill_in_missing_metdata(metdata, met_key, date_range, metstation_freq, interp_method)
            logger.trace(f"{metdata[:10]=}")
            logger.trace(f"{metdata[-10:]=}")
        metstation_df = build_metstation_df(met_key, metdata, date_range)
        # Getting rid of negative global irradiance values from the instrument
        metstation_df.loc[metstation_df['global_shortwave'] < 0, 'global_shortwave'] = 0.0
        metstation_df.loc[metstation_df['direct_shortwave'] < 0, 'direct_shortwave'] = 0.0
        metstation_df.loc[metstation_df['diffuse_shortwave'] < 0, 'diffuse_shortwave'] = 0.0

        logger.trace(f"{metstation_df[:10]=}")
        logger.trace(f"{metstation_df[-10:]=}")
    elif met_key:
        raise ValueError("No met station data provided to pull met parameters from")
    else:
        metstation_df = None
    return metstation_df

def build_metstation_df(met_key: Dict[str, str], metdata: pd.DataFrame, date_range: List[datetime.datetime]) \
        -> pd.DataFrame:

    met_station_df = pd.DataFrame(index=date_range)

    for parameter, key in met_key.items():
        if key in metdata.columns:
            try:
                met_station_df[parameter] = metdata.loc[met_station_df.index, key]
            except KeyError as e:
                if "DatetimeIndex" in str(e):
                    logger.error(
                        "Time mismatch error: The time index in the dataframe does not match the time index you are trying to assign.")
                    logger.error(f"Met Data Start: {metdata.index.min()}, End: {metdata.index.max()}")
                    logger.error(f"Your Start: {met_station_df.index.min()}, End: {met_station_df.index.max()}")
                    logger.error(f"{metdata[:10]=}")
                    logger.error(f"{metdata[-10:]=}")
                else:
                    logger.error(f"Key error: The key '{key}' does not exist in the dataframe.")
                raise e
    return met_station_df

def fill_in_missing_metdata(
        metdata: pd.DataFrame,
        met_key: Dict[str, str],
        date_range: pd.DatetimeIndex,
        metstation_freq: str,
        interp_method: str,
        wind_avg_method: str = "legacy_scalar",
        calm_threshold_mps: float = 0.2,
) -> pd.DataFrame:
    # keep only columns we intend to resample; coerce numeric
    metdata = metdata[met_key.values()]
    for col in metdata.columns:
        metdata.loc[:, col] = pd.to_numeric(metdata.loc[:, col], errors='coerce')

    # map raw column name -> parameter name (e.g., 'Precip' -> 'precipitation')
    col_to_param: dict[str, str] = {v: k for k, v in met_key.items()}

    # interpolate at native cadence
    met_native = metdata.resample(metstation_freq).interpolate(method=interp_method)

    # default aggregation: mean; precipitation -> sum
    aggregation_methods = {
        col: ("sum" if col_to_param.get(col) == "precipitation" else "mean")
        for col in met_native.columns
    }

    # aggregate to output cadence
    met_agg = met_native.resample(date_range.freq).aggregate(aggregation_methods)
    logger.trace(f"metdata after resample: {met_agg}")

    # optional: vector-mean wind override
    if wind_avg_method == "vector":
        spd_col = met_key.get("wind_speed")
        dir_col = met_key.get("wind_direction")
        if spd_col in met_native.columns and dir_col in met_native.columns:
            spd_native = met_native[spd_col].to_numpy(dtype=float)
            dir_native = met_native[dir_col].to_numpy(dtype=float)
            th_rad     = np.deg2rad(dir_native)

            u_native = -spd_native * np.sin(th_rad)
            v_native = -spd_native * np.cos(th_rad)  # <-- fix sign

            u_series = pd.Series(u_native, index=met_native.index)
            v_series = pd.Series(v_native, index=met_native.index)

            u_bar = u_series.resample(date_range.freq).mean().reindex(date_range)
            v_bar = v_series.resample(date_range.freq).mean().reindex(date_range)

            spd_vec = np.hypot(u_bar, v_bar)
            dir_vec = (np.degrees(np.arctan2(-u_bar, -v_bar)) % 360.0)
            dir_vec = dir_vec.where(spd_vec >= float(calm_threshold_mps), np.nan)

            met_agg.loc[:, spd_col] = spd_vec.to_numpy()
            met_agg.loc[:, dir_col] = dir_vec.to_numpy()
        else:
            logger.debug("Vector-mean requested but wind columns not present; using scalar means.")

    return met_agg.reindex(date_range)

# Read Met Data
def read_metstation_data(metfile: str) -> Union[pd.DataFrame, None]:
    if not metfile:
        return None
    else:
        try:
            logger.info(f"Reading metstation data from {metfile}")
            utc = pytz.UTC
            metdata = pd.read_excel(metfile, skiprows=[1], index_col=0)
            metdata.tz_localize(utc)
            logger.trace(f"{metdata[:10]=}")
            logger.trace(f"{metdata[-10:]=}")
        except ValueError:
            logger.error(f"Could not read metstation data from {metfile}")
            raise
    return metdata
