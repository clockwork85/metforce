from typing import Any, Dict

import pandas as pd

from defaults import default_met_units, default_met_width, default_met_decimal, default_col_names
from logger_config import logger

Parameters = Dict[str, Dict[str, Any]]
def create_header(location_name: str, latitude: float, longitude: float, elevation: float, start_range: str, end_range: str, freq: str) -> str:
    if location_name is None:
        location_name = "Location"
    header = f"{location_name} Met Data from {start_range} to {end_range} at {freq} resolution\n"
    header += f"Elevation(m), Latitude, Longitude, GMT-UTC\n"
    header += f"{elevation}, {latitude}, {longitude}, 0\n"
    return header


def write_met_data(met_df: pd.DataFrame, outfile: str, header: str, parameters: Parameters) -> None:

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

