from datetime import datetime
from typing import Any, Dict

import pandas as pd

from metforce.defaults import default_met_units, default_met_width, default_met_decimal, default_col_names
from metforce.logger_config import logger

Parameters = Dict[str, Dict[str, Any]]
def create_header(location_name: str, latitude: float, longitude: float, elevation: float, start_range: str, end_range: str, freq: str) -> str:
    if location_name is None:
        location_name = "Location"

    # Parse the start_range string using the provided format to get the year
    start_date = datetime.strptime(start_range, "%Y-%m-%d %H:%M")
    year = start_date.year

    header = f"{location_name} Met Data from {start_range} to {end_range} at {freq} resolution\n"
    header += f"Elevation(m), Latitude, Longitude, GMT-UTC, Year\n"
    header += f"{elevation}, {latitude}, {longitude}, 0, {year}\n"
    return header


def write_met_data(met_df: pd.DataFrame, outfile: str, header: str, parameters: Parameters) -> None:
    """
    Writes the met data to the output file.

    Parameters
    ----------
    met_df : pd.DataFrame
        The DataFrame containing the met data.
    outfile : str
        The output file path.
    header : str
        The header string to be written in the output file.
    parameters : Parameters
        Various parameters.

    Returns
    -------
    None
    """

    logger.info(f"Writing met data to {outfile}")
    max_lengths = {}
    # Finding the maximum lengths for each column
    for col in met_df.columns:
        decimals = default_met_decimal.get(col, 0) # default to zero decimal places
        max_length = max(len(f'{item:.{decimals}f}') if isinstance(item, float) else len(str(item)) for item in met_df[col]) + 1
        # Compare with default width and take the larger value
        max_lengths[col] = max(max_length, default_met_width[col])

    units = [default_met_units.get(col) for col in met_df.columns]
    with open(outfile, 'w') as f:
        f.write(header)
        for col in met_df.columns:
            f.write(f'{default_col_names[col]:<{max_lengths[col]}}')
        f.write('\n')

        for col, unit in zip(met_df.columns, units):
            f.write(f'{unit:<{max_lengths[col]}}')
        f.write('\n')

        # Write the sources
        for col in met_df.columns:
            if col == 'day':
                f.write('# Sources - ')
            elif col == 'hour' or col == 'minute':
                continue
            else:
                source = parameters.get(col, {}).get('source', '-')
                f.write(f"{source:<{max_lengths[col]}}")
        f.write('\n')

        for index, row in met_df.iterrows():
            for col, item in zip(met_df.columns, row):
                decimals = default_met_decimal.get(col, 0)
                logger.trace(f"Writing {item} to {col} with {decimals} decimal places")
                try:
                    formatted_item = f'{item:.{decimals}f}'
                except ValueError:
                    formatted_item = f'{item}'
                f.write(f'{formatted_item:<{max_lengths[col]}}')
            f.write('\n')

