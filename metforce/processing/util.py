import datetime
from typing import List, Tuple

import pandas as pd

from metforce.logger_config import logger

def check_for_missing_dates(metdata: pd.DataFrame, date_range: pd.DatetimeIndex) -> List[datetime.datetime]:

    date_range_set = set(date_range)
    metdata_set = set(metdata.index)

    missing_dates = list(date_range_set - metdata_set)

    return missing_dates

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
