from typing import Dict, List, Optional

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

    return pd.DataFrame(global_dict, index=date_range)

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
