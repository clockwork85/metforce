import datetime
from typing import Dict, List, Optional, Union

import pandas as pd
import pytz

from metforce.data_types import Parameters
from metforce.logger_config import logger

# Function for Met Station data processing
def process_metstation_data(parameters: Parameters, metdata: Optional[pd.DataFrame],
                             date_range: pd.DatetimeIndex, metstation_freq: str, interp_method: Optional[str]) \
        -> Optional[pd.DataFrame]:

    if metdata is None:
        logger.debug("No met station data provided")
        return None

    met_key = {key: value["key"] for key, value in parameters.items() if value["source"] == "met"}

    if metdata is not None:
        if interp_method is not None:
            metdata = fill_in_missing_metdata(metdata, met_key, date_range, metstation_freq, interp_method)
            logger.trace(f"{metdata[:10]=}")
            logger.trace(f"{metdata[-10:]=}")
        metstation_df = build_metstation_df(met_key, metdata, date_range)
        # Getting rid of negative global shortwave values from the instrument
        metstation_df.loc[metstation_df['global_shortwave'] < 0, 'global_shortwave'] = 0.0
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
