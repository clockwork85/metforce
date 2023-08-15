from typing import List, Optional, Tuple

import pandas as pd
import pvlib
import pytz

from metforce.data_types import Parameters
from metforce.logger_config import logger
from metforce.processing.util import julian_to_datetime

# Function for PVLib data processing
def process_pvlib_data(parameters: Parameters, date_range: pd.DatetimeIndex,
                       latitude: float, longitude: float) -> Optional[pd.DataFrame]:
    pvlib_parameters = [key for key in parameters.keys() if parameters[key]['source'] == 'pvlib']
    logger.trace(f"{pvlib_parameters=}")

    if not pvlib_parameters:
        return None
    return build_pvlib_df(pvlib_parameters, date_range, latitude, longitude)

# PVLIB
def get_solar_positions(
        year: int,
        julian_day: int,
        hour: int,
        minute: int,
        latitude: float,
        longitude: float,
) -> Tuple[float, float]:

    date = julian_to_datetime(year, julian_day)
    date = date.replace(hour=hour, minute=minute)

    date_utc = date.replace(tzinfo=pytz.UTC)

    location = pvlib.location.Location(latitude, longitude, tz='UTC')

    solpos = location.get_solarposition(date_utc)

    # solpos = pvlib.solarposition.get_solarposition(date_utc, latitude, longitude)

    return solpos["zenith"], solpos["azimuth"]

def get_zenith_pvlib(
        year: int,
        julian_day: int,
        hour: int,
        minute: int,
        latitude: float,
        longitude: float,
) -> float:

    solpos = get_solar_positions(year, julian_day, hour, minute, latitude, longitude)
    return solpos[0][0]

def get_azimuth_pvlib(
        year: int,
        julian_day: int,
        hour: int,
        minute: int,
        latitude: float,
        longitude: float,
) -> float:

    solpos = get_solar_positions(year, julian_day, hour, minute, latitude, longitude)
    return solpos[1][0]


pvlib_parameter_map = {
    "zenith": get_zenith_pvlib,
    "azimuth": get_azimuth_pvlib,
}
def build_pvlib_df(parameters: List[str], date_range: pd.DatetimeIndex, latitude: float, longitude: float) -> pd.DataFrame:
    # Build the pvlib dataframe
    parameter_series_dict = {
        parameter: pd.Series(
            [
                pvlib_parameter_map[parameter](
                    year=date.year,
                    julian_day=date.timetuple().tm_yday,
                    hour=date.hour,
                    minute=date.minute,
                    latitude=latitude,
                    longitude=longitude,
                )
                for date in date_range
            ],
            index=date_range,
            name=None,
        )
        for parameter in parameters
        if parameter in pvlib_parameter_map
    }
    if len(parameter_series_dict) != len(parameters):
        missing_parameters = set(parameters) - set(parameter_series_dict.keys())
        raise KeyError(f"The following parameters are not supported by any pvlib functions: {missing_parameters}")
    pvlib_df = pd.DataFrame(parameter_series_dict)
    return pvlib_df

