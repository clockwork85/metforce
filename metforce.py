import datetime
from enum import Enum
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple, Union

from loguru import logger
import pandas as pd
import pvlib
import pytz

from metforce_config import parse_config
from metforce_defaults import default_col_names, default_met_units, default_met_decimal, default_met_width
from metforce_grib import build_grib_df, pull_grib_files


# Set to DEBUG for more verbose logging
# Set to TRACE for even more verbose logging
logger.remove()
logger.add(sys.stderr, level="TRACE")


class Source(Enum):
    GRIB = "grib"
    MET = "met"
    PVLIB = "pvlib"
    GLOBAL = "global"

# GRIB helper function
def get_grib_dates(metdata: pd.DataFrame, parameters: Dict[str, Dict], date_range: pd.DatetimeIndex,
                   interp_method: Union[str, bool], pull_grib: bool) -> List[datetime.datetime]:
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

# Function for GRIB data processing
def process_grib_data(parameters: Dict[str, Dict[str, str]], date_range: pd.DatetimeIndex, latitude: float,
                      longitude: float, tmp_grib_folder: str, pull_grib: bool, cleanup_folder: bool,
                      interp_method: Optional[Union[str, None]]=None) -> Optional[pd.DataFrame]:

    grib_dates = get_grib_dates(metdata, parameters, date_range, interp_method, pull_grib)
    grib_files_and_dates_dict = pull_grib_files(grib_dates, latitude, longitude, tmp_grib_folder, cleanup_folder)
    grib_parameters = [key for key in parameters.keys() if parameters[key]['source'] == 'grib']

    if grib_parameters:
        grib_df = build_grib_df(grib_parameters, grib_files_and_dates_dict, latitude, longitude)
        logger.trace(f"{grib_df=}")
    else:
        grib_df = None
    return grib_df

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

# Function for Global data processing
def process_global_data(parameters: Dict[str, Dict[str, str]], date_range: pd.DatetimeIndex,
                        dataframes: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
    global_parameters = [key for key in parameters.keys() if parameters[key]['source'].startswith('global')]
    logger.trace(f"{global_parameters=}")

    if global_parameters:
        global_parameters, parameters = modify_global_parameters(global_parameters, parameters)
        global_source = parameters['global_shortwave']['source']
        global_shortwave = dataframes[global_source]['global_shortwave']
        global_df = build_global_df(global_parameters, date_range, global_shortwave)
    else:
        global_df = None
    return global_df, parameters

# Helper function to modify global parameters
def modify_global_parameters(global_parameters: List[str], parameters: Dict[str, Dict[str, str]]) -> Tuple[Dict[str, float], Dict[str, Dict[str, str]]]:
    global_parameters_dict = {}
    for key in global_parameters:
        if parameters[key]['source'].startswith('global'):
            fraction = float(parameters[key]['source'].split('_')[1][:-1]) / 100.0
            parameters[key]['source'] = 'global'
            global_parameters_dict[key] = fraction
    logger.trace(f"{global_parameters_dict=}")
    return global_parameters_dict, parameters


# Helper functions
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

# Read Met Data
def read_metstation_data(metfile: str) -> pd.DataFrame:
    utc = pytz.UTC
    metdata = pd.read_excel(metfile, skiprows=[1], index_col=0)
    metdata.tz_localize(utc)
    logger.trace(f"{metdata[:50]=}")
    return metdata


def merge_met_dataframes(parameters: Dict[str, Dict[str, str]], dataframes: Dict[str, pd.DataFrame]) -> pd.DataFrame:
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

# Function for Met Station data processing
def process_met_station_data(parameters: Dict[str, Dict[str, str]], metdata: Optional[pd.DataFrame],
                             date_range: pd.DatetimeIndex, metstation_freq: str, interp_method: Optional[str]) \
        -> Optional[pd.DataFrame]:

    if metdata is None:
        logger.debug("No met station data provided")
        return None

    met_key = {key: value["key"] for key, value in parameters.items() if value["source"] == "met"}

    if metdata is not None:
        if interp_method is not None:
            metdata = fill_in_missing_metdata(metdata, met_key, date_range, metstation_freq, interp_method)
            logger.trace(f"{metdata[:50]=}")
        metstation_df = build_metstation_df(met_key, metdata, date_range)
        logger.trace(f"{metstation_df[:50]=}")
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
                    logger.error(f"{metdata[:50]=}")
                else:
                    logger.error(f"Key error: The key '{key}' does not exist in the dataframe.")
                raise e
    return met_station_df

def create_header(location_name: str, latitude: float, longitude: float, elevation: float, start_range: str, end_range: str, freq: str) -> str:
    if location_name is None:
        location_name = "Location"
    header = f"{location_name} Met Data from {start_range} to {end_range} at {freq} resolution\n"
    header += f"Elevation(m), Latitude, Longitude, GMT-UTC\n"
    header += f"{elevation}, {latitude}, {longitude}, 0\n"
    return header

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

def write_met_data(met_df: pd.DataFrame, outfile: str, header: str, parameters: Dict[str, Dict[str, str]]) -> None:

    logger.info(f"Writing met data to {outfile}")
    max_lengths = {}
    units = [default_met_units.get(col) for col in met_df.columns]
    # met_df.rename(columns=default_col_names, inplace=True)
    with open(outfile, 'w') as f:
        f.write(header)
        for col in met_df.columns:
            f.write(f'{default_col_names[col]:<{default_met_width[col]}}')
        f.write('\n')

        for col, unit in zip(met_df.columns, units):
            f.write(f'{unit:<{default_met_width[col]}}')
        f.write('\n')

        # Write the sources
        for col in met_df.columns:
            if col == 'day':
                f.write('# Sources - ')
            elif col == 'hour' or col == 'minute':
                continue
            else:
                source = parameters.get(col, {}).get('source', '-')
                f.write(f"{source:<{default_met_width[col]}}")
        f.write('\n')

        for index, row in met_df.iterrows():
            for col, item in zip(met_df.columns, row):
                decimals = default_met_decimal.get(col, 0) # default to zero decimal places
                logger.trace(f"Writing {item} to {col} with {decimals} decimal places")
                try:
                    formatted_item = f'{item:.{decimals}f}'
                except ValueError:
                    formatted_item = f'{item}'
                f.write(f'{formatted_item:<{default_met_width[col]}}')
            f.write('\n')


# def process_met(latitude: float,
#                 longitude: float,
#                 elevation: float,
#                 start_range: str,
#                 end_range: str,
#                 outfile: str,
#                 tmp_grib_folder: str,
#                 cleanup_folder: bool,
#                 location_name: str,
#                 freq: str,
#                 pull_grib: bool,
#                 interp_method: Union[None, str],
#                 metstation_freq: str,
#                 parameters: Dict[str, Dict[str, str]],
#                 metdata: Optional[pd.DataFrame] = None,
#                 ) -> pd.DataFrame:
#     dataframes = {}
#     # Create the date range based on the start and end range and the frequency
#     date_range = get_date_range(start_range, end_range, freq)
#
#     # Create key with met parameters mapped to the key in the metdata dataframe
#     met_key = {key: value["key"] for key, value in parameters.items() if value["source"] == "met"}
#
#     logger.trace(f"{met_key=}")
#     # If met station data is provided, then check for missing dates and fill in the missing dates using interpolation
#     if metdata is not None and interp_method is not None:
#         metdata = fill_in_missing_metdata(metdata, met_key, date_range, metstation_freq, interp_method)
#         logger.trace(f"{metdata[:50]=}")
#         metstation_df = build_metstation_df(met_key, metdata, date_range)
#     elif metdata is not None and interp_method is None:
#         metstation_df = build_metstation_df(met_key, metdata, date_range)
#     elif metdata is None and met_key:
#         raise ValueError("No met station data provided to pull met parameters from")
#     else:
#         metstation_df = None
#
#     if metstation_df is not None:
#         logger.trace(f"{metstation_df.head()=}")
#         dataframes[Source.MET.value] = metstation_df
#
#     # Go through the many cases where we might want to pull GRIB files
#     grib_dates = get_grib_dates(metdata, parameters, date_range, interp_method, pull_grib)
#     grib_files_and_dates_dict = pull_grib_files(grib_dates, latitude, longitude, tmp_grib_folder, cleanup_folder)
#     grib_parameters = [key for key in parameters.keys() if parameters[key]['source'] == 'grib']
#
#     # Build grib dataframe
#     if grib_parameters:
#         grib_df = build_grib_df(grib_parameters, grib_files_and_dates_dict, latitude, longitude)
#         logger.trace(f"{grib_df=}")
#     else:
#         grib_df = None
#     if grib_df is not None:
#         dataframes[Source.GRIB.value] = grib_df
#
#     # Build pvlib dataframe
#     pvlib_parameters = [key for key in parameters.keys() if parameters[key]['source'] == 'pvlib']
#     logger.trace(f"{pvlib_parameters=}")
#
#     if pvlib_parameters:
#         pvlib_df = build_pvlib_df(pvlib_parameters, date_range, latitude, longitude)
#     else:
#         pvlib_df = None
#
#     if pvlib_df is not None:
#         dataframes[Source.PVLIB.value] = pvlib_df
#
#     global_parameters = [key for key in parameters.keys() if parameters[key]['source'].startswith('global')]
#     logger.trace(f"{global_parameters=}")
#
#     if global_parameters:
#         global_parameters = {}
#         # Replace global_*% with global in the parameters
#         for key in parameters.keys():
#             if parameters[key]['source'].startswith('global'):
#                 fraction = float(parameters[key]['source'].split('_')[1][:-1]) / 100.0
#                 parameters[key]['source'] = 'global'
#                 global_parameters[key] = fraction
#         logger.trace(f"{global_parameters=}")
#         global_source = parameters['global_shortwave']['source']
#         global_shortwave = dataframes[global_source]['global_shortwave']
#         global_df = build_global_df(global_parameters, date_range, global_shortwave)
#     else:
#         global_df = None
#
#     if global_df is not None:
#         logger.trace(f"{global_df=}")
#         dataframes[Source.GLOBAL.value] = global_df
#
#
#     # Remove the dataframe keys whose values are None
#     dataframes = {key: value for key, value in dataframes.items() if value is not None}
#
#     # Build the new dataframe with the DateTimes as the index to add columns to
#     met_df = merge_met_dataframes(parameters, dataframes)
#
#     # Create the header for the output file
#     header = create_header(location_name, latitude, longitude, elevation, start_range, end_range, freq)
#     logger.trace(f"{header=}")
#
#     # Add unused columns to the dataframe like Visibility, Aerosol, Cloud Cover, etc.
#     met_df = add_unused_columns(met_df)
#
#     # Add the date columns to the dataframe from the index
#     met_df = add_date_columns(met_df)
#
#     # Reorder the columns to match the default column order
#     met_df = met_df[list(default_col_names.keys())]
#     logger.trace(f"{met_df=}")
#
#     logger.trace(f"{met_df.relative_humidity=}")
#     # Write the dataframe to the output file
#     write_met_data(met_df, outfile, header, parameters)

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

def process_met_data(latitude: float,
                longitude: float,
                elevation: float,
                start_range: str,
                end_range: str,
                outfile: str,
                tmp_grib_folder: str,
                cleanup_folder: bool,
                location_name: str,
                freq: str,
                pull_grib: bool,
                interp_method: Union[None, str],
                metstation_freq: str,
                parameters: Dict[str, Dict[str, str]],
                metdata: Optional[pd.DataFrame] = None,
                ) -> Tuple[pd.DataFrame, Dict[str, Dict[str, str]]]:

    date_range = pd.date_range(start=start_range, end=end_range, freq=freq)

    dataframes = {}

    dataframes[Source.MET.value] = process_met_station_data(parameters, metdata, date_range, metstation_freq, interp_method)
    logger.trace(f"{dataframes[Source.MET.value]=}")
    dataframes[Source.GRIB.value] = process_grib_data(parameters, date_range, latitude, longitude,
                                                      tmp_grib_folder, pull_grib, cleanup_folder, interp_method)
    logger.trace(f"{dataframes[Source.GRIB.value]=}")

    dataframes[Source.PVLIB.value] = process_pvlib_data(parameters, date_range, latitude, longitude)
    logger.trace(f"{dataframes[Source.PVLIB.value]=}")

    dataframes[Source.GLOBAL.value], parameters = process_global_data(parameters, date_range, dataframes)
    logger.trace(f"{dataframes[Source.GLOBAL.value]=}")

    met_df = merge_and_prepare_for_output(parameters, dataframes, location_name, latitude, longitude,
                                 elevation, start_range, end_range, freq, outfile)
    return met_df, parameters


if __name__ == "__main__":
    config = parse_config("config/test_met.toml")
    logger.debug(f"{config=}")
    if config.optional.metfile:
        metdata = read_metstation_data(config.optional.metfile)
    else:
        logger.trace("No metfile provided")
        metdata = None
    required = config.required
    optional = config.optional
    parameters = config.parameters.parameters
    met_df, parameters = process_met_data(required.latitude, required.longitude, required.elevation, required.start_range, required.end_range,
                optional.outfile, optional.tmp_grib_folder, optional.cleanup_folder, optional.location_name,
                optional.freq, optional.pull_grib, optional.interp_method, optional.metstation_freq, parameters, metdata)
    # Create the header for the output file
    header = create_header(optional.location_name, required.latitude, required.longitude, required.elevation, required.start_range, required.end_range, optional.freq)
    logger.trace(f"{header=}")
    write_met_data(met_df, optional.outfile, header, parameters)
