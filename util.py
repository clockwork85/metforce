import datetime
from typing import Dict, List, Tuple, Union

import pandas as pd

from logger_config import logger



# GRIB helper function
def get_grib_dates(metdata: pd.DataFrame, parameters: Dict[str, Dict], date_range: pd.DatetimeIndex,
                   interp_method: Union[str, bool], pull_grib: bool) -> List[datetime.datetime]:
    from sources import Source
    # See if there are any parameters that are pulled from GRIB data
    logger.debug(f"From get_grib_dates: {parameters=}")
    any_grib = any(param["source"] == Source.GRIB.value for param in parameters.values())

    if any_grib:
        return date_range

    # If met station data is provided, but no interpolation method is provided, then fill in the missing dates with grib
    # The any_grib is there because if there are grib parameters we will be pulling all the grib data anyway
    if metdata is not None and interp_method is None and pull_grib and not any_grib:
        return check_for_missing_dates(metdata, date_range)

    # If met station data is not provided, then we will be pulling all the grib data
    if metdata is None and pull_grib:
        return date_range

    return []

def check_for_missing_dates(metdata: pd.DataFrame, date_range: pd.DatetimeIndex) -> List[datetime.datetime]:

    date_range_set = set(date_range)
    metdata_set = set(metdata.index)

    missing_dates = list(date_range_set - metdata_set)

    return missing_dates

def fill_in_missing_metdata(metdata: pd.DataFrame, met_key: Dict[str, str], date_range: pd.DatetimeIndex,
                            metstation_freq: str, interp_method: str) -> pd.DataFrame:

    metdata = metdata[met_key.values()]
    for col in metdata.columns:
        metdata.loc[:, col] = pd.to_numeric(metdata.loc[:, col], errors='coerce')

    aggregation_methods = {col: ('sum' if col in met_key.values() and met_key.get(col) == 'precipitation' else 'mean')
                           for col in metdata.columns}

    metdata = metdata.resample(metstation_freq).interpolate(method=interp_method)
    logger.trace(f"metdata after interpolate: {metdata}")
    metdata = metdata.resample(date_range.freq).aggregate(aggregation_methods)
    logger.trace(f"metdata after resample: {metdata}")
    return metdata.reindex(date_range)

# Helper function to modify global parameters
def modify_global_parameters(global_parameters: List[str], parameters: Dict[str, Dict[str, str]]) -> Dict[str, float]:
    global_parameters_dict = {}
    for key in global_parameters:
        if parameters[key]['source'].startswith('global'):
            fraction = float(parameters[key]['source'].split('_')[1][:-1]) / 100.0
            parameters[key]['source'] = 'global'
            global_parameters_dict[key] = fraction
    logger.trace(f"{global_parameters_dict=}")
    return global_parameters_dict

def julian_to_datetime(year: int, julian_date: int) -> datetime:
    return datetime.datetime(year, 1, 1) + datetime.timedelta(julian_date - 1)

def convert_str_to_datetime(start_range: str, end_range: str) -> Tuple[datetime.datetime, datetime.datetime]:

    fmt = "%Y-%m-%d %H:%M"
    start = pd.to_datetime(start_range, format=fmt)
    end = pd.to_datetime(end_range, format=fmt)

    return start, end

def get_date_range(start_range: str, end_range: str, freq: str) -> pd.DatetimeIndex:

    start, end = convert_str_to_datetime(start_range, end_range)

    return pd.date_range(start=start, end=end, freq=freq)

def get_date_range_grib(start_range: str, end_range: str, freq: str) -> pd.DatetimeIndex:

    one_hour = pd.to_timedelta("1H")
    freq_timedelta = pd.to_timedelta(freq)
    grib_freq = one_hour if freq_timedelta < one_hour else freq_timedelta

    start, end = convert_str_to_datetime(start_range, end_range)

    return pd.date_range(start=start, end=end, freq=grib_freq)

def add_unused_columns(met_df: pd.DataFrame) -> pd.DataFrame:

    met_df['visibility'] = -9.9
    met_df['aerosol'] = 10.0
    met_df['cloud_cover_1'] = 0.00
    met_df['cloud_cover_2'] = 0.00
    met_df['cloud_cover_3'] = 0.00
    met_df['cloud_cover_4'] = 0.00
    met_df['cloud_cover_5'] = 0.00
    met_df['cloud_cover_6'] = 0.00
    met_df['cloud_cover_7'] = 0.00

    return met_df

def add_date_columns(met_df: pd.DataFrame) -> pd.DataFrame:

    # 3 Digit Julian day of year with 0 padding on left
    met_df['day'] = met_df.index.strftime('%j')
    met_df['hour'] = met_df.index.strftime('%H')
    met_df['minute'] = met_df.index.strftime('%M')

    return met_df
