import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pvlib
import pytz

from defaults import default_col_names
from logger_config import logger
from util import add_date_columns, add_unused_columns, fill_in_missing_metdata, get_grib_dates, julian_to_datetime, \
    modify_global_parameters
from grib import build_grib_df, pull_grib_files

Parameters = Dict[str, Dict[str, str]]


# Function for GRIB data processing
def process_grib_data(parameters: Dict[str, Dict[str, str]], metdata: pd.DataFrame, date_range: pd.DatetimeIndex,
                      latitude: float, longitude: float, tmp_grib_folder: str, pull_grib: bool, cleanup_folder: bool,
                      interp_method: Optional[str] = None) -> Optional[pd.DataFrame]:

    grib_dates = get_grib_dates(metdata, parameters, date_range, interp_method, pull_grib)
    grib_files_and_dates_dict = pull_grib_files(grib_dates, latitude, longitude, tmp_grib_folder, cleanup_folder)
    grib_parameters = [key for key in parameters.keys() if parameters[key]['source'] == 'grib']

    if grib_parameters:
        grib_df = build_grib_df(grib_parameters, grib_files_and_dates_dict, latitude, longitude)
        logger.trace(f"{grib_df=}")
    else:
        grib_df = None
    return grib_df



# Function for PVLib data processing
def process_pvlib_data(parameters: Dict[str, Dict[str, str]], date_range: pd.DatetimeIndex,
                       latitude: float, longitude: float) -> Optional[pd.DataFrame]:
    pvlib_parameters = [key for key in parameters.keys() if parameters[key]['source'] == 'pvlib']
    logger.trace(f"{pvlib_parameters=}")

    if pvlib_parameters:
        pvlib_df = build_pvlib_df(pvlib_parameters, date_range, latitude, longitude)
    else:
        pvlib_df = None
    return pvlib_df

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

    solpos = pvlib.solarposition.get_solarposition(date_utc, latitude, longitude)

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



# Function for Global data processing
def process_global_data(parameters: Dict[str, Dict[str, str]], date_range: pd.DatetimeIndex,
                        dataframes: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
    global_parameters = [key for key in parameters.keys() if parameters[key]['source'].startswith('global')]
    logger.trace(f"{global_parameters=}")

    if global_parameters:
        global_parameters = modify_global_parameters(global_parameters, parameters)
        global_source = parameters['global_shortwave']['source']
        global_shortwave = dataframes[global_source]['global_shortwave']
        global_df = build_global_df(global_parameters, date_range, global_shortwave)
    else:
        global_df = None
    return global_df

def build_global_df(
        parameters: Dict[str, Dict],
        date_range: pd.DatetimeIndex,
        global_shortwave: pd.Series
) -> pd.DataFrame:

    logger.trace(f"From build_global_df: {parameters=}")
    logger.trace(f"Global shortwave: {global_shortwave=}")
    global_dict = {}
    for parameter, fraction in parameters.items():
        global_dict[parameter] = global_shortwave * fraction

    if len(global_dict) != len(parameters):
        missing_parameters = set(parameters) - set(global_dict.keys())
        raise KeyError(f"The following parameters are not supported by any pvlib functions: {missing_parameters}")

    return pd.DataFrame(global_dict, index=date_range)


# Function to merge dataframes and prepare for output
def merge_and_prepare_for_output(parameters: Dict[str, Dict[str, str]], dataframes: Dict[str, pd.DataFrame],
                                 location_name: str, latitude: float, longitude: float,
                                 elevation: float, start_range: str, end_range: str, freq: str, outfile: str):
    # Remove the dataframe keys whose values are None
    dataframes = {key: value for key, value in dataframes.items() if value is not None}

    # Build the new dataframe with the DateTimes as the index to add columns to
    met_df = merge_met_dataframes(parameters, dataframes)

    # Create the header for the output file
    # header = create_header(location_name, latitude, longitude, elevation, start_range, end_range, freq)
    # logger.trace(f"{header=}")

    # Add unused columns to the dataframe like Visibility, Aerosol, Cloud Cover, etc.
    met_df = add_unused_columns(met_df)

    # Add the date columns to the dataframe from the index
    met_df = add_date_columns(met_df)

    # Reorder the columns to match the default column order
    met_df = met_df[list(default_col_names.keys())]
    logger.trace(f"{met_df=}")

    logger.trace(f"{met_df.relative_humidity=}")
    # Write the dataframe to the output file
    return met_df


def merge_met_dataframes(parameters: Parameters, dataframes: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    # Get first dataframe to use as index
    index = list(dataframes.values())[0].index
    merged_df = pd.DataFrame(index=index, columns=parameters)
    logger.trace(f"Parameters from merge_met_dataframes: {parameters}")
    logger.trace(f"Parameters from merge_met_dataframes: {type(parameters)}")
    for parameter in parameters.keys():
        source = parameters[parameter]['source']
        df = dataframes[source]
        try:
            logger.trace(f"Trying to merge {parameter} from {source}")
            merged_df[parameter] = df[parameter]
        except KeyError as e:
            logger.trace(f"Parameter {parameter} not found in dataframe {source}")
            raise e
    return merged_df
