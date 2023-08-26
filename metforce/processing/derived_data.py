from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from metforce.data_types import Parameters
from metforce.logger_config import logger

# Function for Global data processing
def process_global_data(parameters: Parameters, date_range: pd.DatetimeIndex,
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
        global_parameters: Dict[str, float],
        date_range: pd.DatetimeIndex,
        global_shortwave: pd.Series
) -> pd.DataFrame:

    logger.trace(f"From build_global_df: {global_parameters=}")
    logger.trace(f"Global shortwave: {global_shortwave=}")
    global_dict = {}
    for parameter, fraction in global_parameters.items():
        global_dict[parameter] = global_shortwave * fraction

    if len(global_dict) != len(global_parameters):
        missing_parameters = set(global_parameters) - set(global_dict.keys())
        raise KeyError(f"The following parameters are not supported by any pvlib functions: {missing_parameters}")
    logger.info(f"Global dataframe built with parameters: {', '.join(list(global_dict.keys())).rstrip(', ')}")
    return pd.DataFrame(global_dict, index=date_range)

def build_brunt_df(
        brunt_parameters: List[str],
        date_range: pd.DatetimeIndex,
        temperature: pd.Series,
        relative_humidity: pd.Series
) -> pd.DataFrame:

    logger.trace(f"From build_brunt_df: {brunt_parameters=}")
    logger.trace(f"{temperature=}")
    logger.trace(f"{relative_humidity=}")
    brunt_dict = {}
    for parameter in brunt_parameters:
        brunt_dict[parameter] = calculate_dlr_brunt(temperature, relative_humidity)

    if len(brunt_dict) != len(brunt_parameters):
        missing_parameters = set(brunt_parameters) - set(brunt_dict.keys())
        raise KeyError(f"The following parameters are not supported by any pvlib functions: {missing_parameters}")
    logger.info(f"Global dataframe built with parameters: {', '.join(list(brunt_dict.keys())).rstrip(', ')}")
    return pd.DataFrame(brunt_dict, index=date_range)

# Helper function to modify global parameters
def modify_global_parameters(global_parameters: List[str], parameters: Parameters) -> Dict[str, float]:
    global_parameters_dict = {}
    for key in global_parameters:
        if parameters[key]['source'].startswith('global'):
            fraction = float(parameters[key]['source'].split('_')[1][:-1]) / 100.0
            parameters[key]['source'] = 'global'
            global_parameters_dict[key] = fraction
    logger.trace(f"{global_parameters_dict=}")
    return global_parameters_dict

def process_brunt_data(parameters: Parameters, date_range: pd.DatetimeIndex,
                        dataframes: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
    brunt_parameters = [key for key in parameters.keys() if parameters[key]['source'].startswith('brunt')]
    logger.trace(f"{brunt_parameters=}")

    if brunt_parameters:
        # brunt_parameters = modify_brunt_parameters(brunt_parameters, parameters)
        temp_source = parameters['temperature']['source']
        temperature = dataframes[temp_source]['temperature']
        relative_humidity_source = parameters['relative_humidity']['source']
        relative_humidity = dataframes[relative_humidity_source]['relative_humidity']
        brunt_df = build_brunt_df(brunt_parameters, date_range, temperature, relative_humidity)
    else:
        brunt_df = None
    return brunt_df

# def modify_brunt_parameters(brunt_parameters: List[str], parameters: Parameters) -> Dict[str, float]:
#     brunt_parameters_dict = {}
#     for key in brunt_parameters:
#         if parameters[key]['source'].startswith('brunt'):
#             temperature = parameters['temperature']['source']
#             logger.trace(f"{temperature=}")
#             relative_humidity = parameters['relative_humidity']['source']
#             logger.trace(f"{relative_humidity=}")
#             lw_downwelling = calculate_dlr_brunt(temperature, relative_humidity)
#             parameters[key]['source'] = 'brunt'
#             brunt_parameters_dict[key] = lw_downwelling
#     logger.trace(f"{brunt_parameters_dict=}")
#     return brunt_parameters_dict


def calculate_dlr_brunt(temp_celsius: pd.Series, relative_humidity: pd.Series) -> pd.Series:
    """
    Calculates downwelling longwave radiation (DLR) using the Brunt equation.

    Parameters
    ----------
    temp_celsius : pd.Series
        Temperature in Celsius.
    relative_humidity : pd.Series
        Relative humidity in percentage (0 to 100).

    Returns
    -------
    pd.Series
        Downwelling longwave radiation in W/m^2.
    """
    stefan_boltzmann_constant = 5.67e-8
    temp_kelvin = temp_celsius + 273.15
    saturation_vapor_pressure = 6.11 * np.exp(5420 * (1/273.15 - 1/temp_kelvin))
    vapor_pressure = saturation_vapor_pressure * relative_humidity / 100
    emissivity = 0.785 - 0.00246 * temp_kelvin + 0.0000129 * temp_kelvin**2
    effective_emissivity = emissivity + 0.0224 * np.sqrt(vapor_pressure)
    return effective_emissivity * stefan_boltzmann_constant * temp_kelvin**4
