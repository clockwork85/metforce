from typing import Dict

import pandas as pd

from metforce.data_types import Parameters
from metforce.defaults import default_col_names
from metforce.logger_config import logger
from metforce.processing.util import add_date_columns, add_unused_columns, julian_to_datetime
from metforce.processing.grib import build_grib_df, pull_grib_files


# Function to merge dataframes and prepare for output
def merge_and_prepare_for_output(parameters: Dict[str, Dict[str, str]],
                                 dataframes: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    # Remove the dataframe keys whose values are None
    dataframes = {key: value for key, value in dataframes.items() if value is not None}

    # Build the new dataframe with the DateTimes as the index to add columns to
    met_df = merge_met_dataframes(parameters, dataframes)

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
        try:
            df = dataframes[source]
        except KeyError as e:
            logger.error(
                f"Source {source} method does not exist. Edit your config file to change the source or add the method to deal with this new source.")
            raise e
        try:
            logger.trace(f"Trying to merge {parameter} from {source}")
            merged_df[parameter] = df[parameter]
        except KeyError as e:
            logger.error(f"Parameter {parameter} not found in dataframe {source}")
            raise e
    return merged_df
