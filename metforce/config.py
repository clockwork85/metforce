from datetime import datetime
from typing import Any, Optional, Dict

from pydantic import BaseModel, Field, validator, root_validator
import toml

from data_types import Parameters
from defaults import (
    default_met,
    default_met_keys,
    default_met_sources,
    default_met_grib,
    default_optional_met,
)
from logger_config import logger

class RequiredConfig(BaseModel):
    """Required Metforce configuration parameters"""

    latitude: float = Field(..., description="Latitude of the location")
    longitude: float = Field(..., description="Longitude of the location")
    elevation: float = Field(..., description="Elevation of the location")
    start_range: str = Field(
        ...,
        description="Start date of the meteorological data in '%Y-%m-%d %H:%M' format",
    )
    end_range: str = Field(
        ...,
        description="End date of the meteorological data in '%Y-%m-%d %H:%M' format",
    )

    @validator("start_range", "end_range", pre=True)
    def parse_dates(cls, v):
        try:
            return datetime.strptime(v, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError("Incorrect date format, should be YYYY-MM-DD HH:MM")


class OptionalConfig(BaseModel):
    # Optional parameters
    outfile: Optional[str] = Field(
        "test.met", description="Filename of the output file"
    )
    metfile: Optional[str] = Field("met", description="Path to the met excel file")
    location_name: Optional[str] = Field(None, description="Name of the location - this can be any colloquial name as it is only used for the header of the output file")
    tmp_grib_folder: Optional[str] = Field(
        "~/tmp_grib_folder", description="Path to the temporary grib folder"
    )
    cleanup_folder: Optional[bool] = Field(
        False, description="Whether to cleanup the temporary grib folder"
    )
    freq: Optional[str] = Field(
        "1H", description="Frequency of the meteorological data"
    )
    pull_grib: Optional[bool] = Field(
        False,
        description="Whether to pull the grib files from the internet if dates missing from met station",
    )
    interp_method: Optional[str] = Field(
        "time", description="Interpolation method for missing data"
    )
    metstation_freq: Optional[str] = Field(
        # https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#timeseries-offset-aliases
        "5T",
        description="Frequency of the met station data",
    )

    @root_validator(pre=True)
    def fill_optional(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        optional = values
        if optional is None:
            logger.info(
                "No optional parameters specified, using default optional parameters"
            )
            values = default_optional_met

        for default_param in default_optional_met.keys():
            if default_param not in optional:
                logger.debug(
                    f"Parameter {default_param} not in default optional met parameters, using default optional met parameters"
                )
                values[default_param] = default_optional_met[default_param]

        logger.debug(f"Optional parameters: {values}")
        return values


class ParametersConfig(BaseModel):

    parameters: Optional[Parameters] = Field(
        None, description="Dictionary of parameters to pull from which model"
    )


class MetforceConfig(BaseModel):
    """Metforce configuration class"""

    required: RequiredConfig
    optional: OptionalConfig
    parameters: ParametersConfig

    @root_validator(pre=True)
    def fill_in_default_met(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        parameters = values.get("parameters")
        metfile = (
            values.get("optional", {}).get("metfile")
            if values.get("optional")
            else None
        )

        # Checking if parameters are not provided but a metfile is provided
        if parameters is None and metfile:
            logger.info("No parameters specified, using default met parameters")
            values["parameters"] = default_met
            parameters = values.get("parameters")

        # Checking if parameters and metfile are not provided
        if parameters is None and metfile is None:
            logger.info(
                "No parameters specified and no metfile, using all GRIB parameters"
            )
            values["parameters"] = default_met_grib
            parameters = values.get("parameters")

        # Checking for parameters that were not provided
        for default_param in default_met.keys():
            logger.trace(f"Checking if {default_param} is in {parameters}")
            if default_param not in parameters:
                logger.debug(
                    f"Parameter {default_param} not in default met parameters, using default met parameters"
                )
                parameters[default_param] = default_met[default_param]

        # Checking for source and key for each parameter - filling in defaults if not provided
        for param, settings in parameters.items():
            if settings.get("source") is None:
                logger.debug("No source specified, using default met source")
                settings["source"] = default_met_sources[param]
            if settings.get("source") == "met" and not settings.get("key"):
                logger.debug(f"No key specified for {param}, using default met key")
                settings["key"] = default_met_keys[param]

        values["parameters"] = {"parameters": parameters}

        return values


def parse_config(file_path: str) -> MetforceConfig:
    """Parse the configuration file"""
    logger.info(f"Parsing configuration file at {file_path}")
    try:
        config = toml.load(file_path)
        return MetforceConfig(**config)
    except Exception as e:
        logger.error(f"Error parsing configuration file: {e}")
        raise e
