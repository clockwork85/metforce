#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from metforce.config import parse_config
from metforce.data_types import Parameters
from metforce.logger_config import logger, set_loglevel
from metforce.output import create_header, write_met_data, build_netcdf_dataset, write_netcdf, write_outputs
from metforce.processing import merge_and_prepare_for_output
from metforce.processing.metstation import read_metstation_data
from metforce.sources import Source, source_strategies


# -----------------------------------------------------------------------------
# Core orchestration
# -----------------------------------------------------------------------------

def process_met_data(
    latitude: float,
    longitude: float,
    start_range: str,
    end_range: str,
    parameters: Parameters,
    *,
    metfile: str | None = None,
    tmp_data_folder: str | None = str(Path.cwd()) + "/metforce_tmp/",
    cleanup_folder: bool = False,
    freq: str | None = None,
    pull_nldas2: bool = True,
    interp_method: str | None = None,
    metstation_freq: str | None = None,
    elevation: float | None = None,
) -> pd.DataFrame:
    """High‑level workflow driver.

    1. Build the *date_range* over which forcing data are required.
    2. Read any provided **met‑station** CSV (can be *None*).
    3. Dispatch to each *source strategy* with a tailored *kwargs* dict.
    4. Merge per‑source DataFrames → final forcing table.
    """

    # 1 ▸ Build the master timeline ------------------------------------------------
    date_range = pd.date_range(start_range, end_range, freq=freq)
    logger.debug(f"Generated {len(date_range)} timestamps between {start_range} and {end_range} using freq={freq!r}")

    # 2 ▸ Read local met‑station data (if provided) --------------------------------
    metdata = read_metstation_data(metfile)

    # 3 ▸ Prepare per‑source argument maps ----------------------------------------
    dataframes: Dict[str, pd.DataFrame | None] = {}

    source_args: Dict[str, Dict[str, Any]] = {
        # Source.GRIB.value: {
        #     "parameters": parameters,
        #     "metdata": metdata,
        #     "date_range": date_range,
        #     "latitude": latitude,
        #     "longitude": longitude,
        #     "tmp_grib_folder": tmp_data_folder,
        #     "cleanup_folder": cleanup_folder,
        #     "interp_method": interp_method,
        # },
        Source.NLDAS2.value: {
            "parameters": parameters,
            "metdata": metdata,
            "date_range": date_range,
            "latitude": latitude,
            "longitude": longitude,
            "tmp_data_folder": tmp_data_folder,
            "pull_nldas2": pull_nldas2,
            "cleanup_folder": cleanup_folder,
            "interp_method": interp_method,
        },
        Source.MET.value: {
            "parameters": parameters,
            "metdata": metdata,
            "date_range": date_range,
            "metstation_freq": metstation_freq,
            "interp_method": interp_method,
        },
        Source.PVLIB.value: {
            "parameters": parameters,
            "date_range": date_range,
            "latitude": latitude,
            "longitude": longitude,
        },
        Source.GLOBAL.value: {
            "parameters": parameters,
            "date_range": date_range,
            "dataframes": dataframes,  # self‑reference for cross‑source ops
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
        },
        Source.BRUNT.value: {
            "parameters": parameters,
            "date_range": date_range,
            "dataframes": dataframes,
        },
    }

    # 4 ▸ Execute each source strategy -------------------------------------------
    for source, strategy in source_strategies.items():
        logger.debug(f"Processing source ⇒ {source}")
        dataframes[source] = strategy.process_data(**source_args[source])

    # 5 ▸ Merge all streams → final df -------------------------------------------
    met_df = merge_and_prepare_for_output(parameters, dataframes)
    logger.info("Meteorological forcing dataframe built with %d rows and %d columns", *met_df.shape)
    return met_df


# -----------------------------------------------------------------------------
# CLI helper – keeps backwards compatibility with original entry‑point
# -----------------------------------------------------------------------------

def _cli() -> None:
    """Command‑line interface that mirrors the original behaviour but
    understands the new NetCDF options."""

    parser = argparse.ArgumentParser(
        description=(
            "Metforce converts remote or local meteorological data sources "
            "into a unified forcing file.  Adjust verbosity with -v / -vv."
        )
    )
    parser.add_argument("config", type=str, help="Path to the TOML configuration file")
    parser.add_argument(
        "-v", "--verbosity", action="count", default=0, help="Logging level: -v=DEBUG, -vv=TRACE"
    )

    args = parser.parse_args()
    set_loglevel(args.verbosity)

    # Parse configuration -------------------------------------------------------
    cfg = parse_config(args.config)
    logger.debug(f"Loaded configuration: {cfg}")

    req = cfg.required
    opt = cfg.optional
    params = cfg.parameters.parameters

    # Map legacy attribute names -------------------------------------------------
    tmp_data_folder = (
        opt.tmp_data_folder if hasattr(opt, "tmp_data_folder") else opt.tmp_grib_folder
    )

    # Run the pipeline -----------------------------------------------------------
    met_df = process_met_data(
        req.latitude,
        req.longitude,
        req.start_range,
        req.end_range,
        params,
        metfile=opt.metfile,
        tmp_data_folder=tmp_data_folder,
        cleanup_folder=opt.cleanup_folder,
        freq=opt.freq,
        pull_nldas2=getattr(opt, "pull_nldas2", True),
        interp_method=opt.interp_method,
        metstation_freq=opt.metstation_freq,
        elevation=opt.elevation,
    )

    # Sanity check for NaNs ------------------------------------------------------
    nan_cols = met_df.columns[met_df.isna().any()].tolist()
    if nan_cols:
        logger.error(f"NaN values detected in columns: {nan_cols}")
        logger.error(f"Head with NaNs:\n{met_df[nan_cols].head()}")
        logger.error(f"Tail with NaNs:\n{met_df[nan_cols].tail()}")
        raise ValueError(f"NaN values found in columns: {nan_cols}")

    # Build header & write output -----------------------------------------------
    header = create_header(
        opt.location_name,
        req.latitude,
        req.longitude,
        req.elevation,
        req.start_range,
        req.end_range,
        opt.freq,
    )
    logger.debug(f"Header prepared:\n{header}")

    out_fmt = getattr(cfg, "output", None).format if hasattr(cfg, "output") else "met"

    netcdf_meta = {
        "title": getattr(cfg.output, "title", None)
                 or f"{opt.location_name or 'Location'} met forcing {req.start_range} to {req.end_range}",
        "institution": getattr(cfg.output, "institution", None) or "MetForce",
        "references": getattr(cfg.output, "references", None),
        "latitude": req.latitude,
        "longitude": req.longitude,
        "elevation_m": req.elevation,
    }


    # -- write legacy .met if requested (default) ---
    write_outputs(
        met_df,
        outfile_met=Path(opt.outfile) if out_fmt in {"met", "both"} else None,
        outfile_nc=Path(opt.outfile).with_suffix(".nc") if out_fmt in {"netcdf", "both"} else None,
        output_format=out_fmt,
        netcdf_meta=netcdf_meta,
        header=header,
        parameters=params,
    )


if __name__ == "__main__":  # pragma: no cover – entry‑point guard
    _cli()

