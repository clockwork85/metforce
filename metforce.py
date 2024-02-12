#!/usr/bin/env python3

#import sys
from typing import Dict, Optional, Tuple

import argparse
import pandas as pd

from metforce.config import parse_config
from metforce.data_types import Parameters
from metforce.logger_config import logger, set_loglevel
from metforce.processing.metstation import read_metstation_data
from metforce.output import create_header, write_met_data
from metforce.processing import merge_and_prepare_for_output
from metforce.sources import source_strategies, Source


def process_met_data(latitude: float,
                longitude: float,
                start_range: str,
                end_range: str,
                metfile: Optional[str],
                tmp_grib_folder: Optional[str],
                cleanup_folder: Optional[bool],
                freq: Optional[str],
                pull_grib: Optional[bool],
                interp_method: Optional[str],
                metstation_freq: Optional[str],
                parameters: Parameters,
                ) -> pd.DataFrame:

    date_range = pd.date_range(start_range, end_range, freq=freq)
    metdata = read_metstation_data(metfile)

    dataframes = {}

    source_args = {
        Source.GRIB.value: {'metdata': metdata, 'date_range': date_range, 'latitude': latitude, 'longitude': longitude,
                            'tmp_grib_folder': tmp_grib_folder, 'pull_grib': pull_grib,
                            'cleanup_folder': cleanup_folder,
                            'interp_method': interp_method},
        Source.MET.value: {'metdata': metdata, 'date_range': date_range, 'metstation_freq': metstation_freq,
                           'interp_method': interp_method},
        Source.PVLIB.value: {'date_range': date_range, 'latitude': latitude, 'longitude': longitude},
        Source.GLOBAL.value: {'date_range': date_range, 'dataframes': dataframes},
        Source.BRUNT.value: {'date_range': date_range, 'dataframes': dataframes}
    }

    for source, strategy in source_strategies.items():
        logger.debug(f"Processing {source}")
        dataframes[source] = strategy.process_data(parameters, **source_args[source])

    met_df = merge_and_prepare_for_output(parameters, dataframes)

    return met_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Metforce takes a config file, and -v for debug logging, and -vv for trace level logging. Info level logging by default.")
    parser.add_argument('config', type=str, help="The toml configuration file.")
    parser.add_argument("-v", "--verbosity", action="count", default=0, help="Set logging level (e.g., -v for DEBUG, -vv for TRACE)")

    args = parser.parse_args()
    set_loglevel(args.verbosity)
    config = parse_config(args.config)

    logger.debug(f"{config=}")
    required = config.required
    optional = config.optional
    parameters = config.parameters.parameters
    met_df = process_met_data(required.latitude, required.longitude,
                                          required.start_range, required.end_range,
                                          optional.metfile,  optional.tmp_grib_folder,
                                          optional.cleanup_folder,  optional.freq,
                                          optional.pull_grib, optional.interp_method, optional.metstation_freq,
                                          parameters)
    nan_columns = met_df.columns[met_df.isna().any()].tolist()
    if nan_columns:
        logger.error(f"NaN values found in columns: {nan_columns}")
        logger.error(f"{met_df[nan_columns].head()}")
        logger.error(f"{met_df[nan_columns].tail()}")
        raise ValueError(f"NaN values found in columns: {nan_columns}")
    # Create the header for the output file
    header = create_header(optional.location_name, required.latitude, required.longitude, required.elevation,
                           required.start_range, required.end_range, optional.freq)
    logger.trace(f"{header=}")
    write_met_data(met_df, optional.outfile, header, parameters)
    logger.success(f"Finished processing met data to output: {optional.outfile}")