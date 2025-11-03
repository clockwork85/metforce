from datetime import datetime
from typing import Any, Optional, Dict

from pydantic import BaseModel, Field, field_validator, model_validator
import toml

from metforce.data_types import Parameters
from metforce.defaults import (
    default_global_fraction,
    default_global_coszenith,
    default_met,
    default_met_keys,
    default_met_sources,
    default_met_grib,
    default_optional_met,
)
from metforce.logger_config import logger

class OutputConfig(BaseModel):
    """Output selection and NetCDF metadata"""

    format: str = Field("both", description="'met' | 'netcdf' | 'both'")
    title: str | None = None
    institution: str | None = None
    references: str | None = None

    @field_validator("format")
    @classmethod
    def _check_format(cls, v: str) -> str:
        allowed = {"met", "netcdf", "both"}
        if v not in allowed:
            raise ValueError(f"Invalid format: {v}")
        return v

class WindConfig(BaseModel):
    """ Wind averaging configuration. """
    avg_method: str= Field("legacy_scalar", description="Wind averaging: 'legacy_scalar' or 'vector'")
    calm_threshold_mps: float = Field(0.2, ge=0.0, description="Calm threshold; direction becomes NaN below this speed")

    @field_validator("avg_method")
    @classmethod
    def _check_method(cls, v: str) -> str:
        allowed = ["legacy_scalar", "vector"]
        if v not in allowed:
            raise ValueError(f"wind.avg_method must be one of {allowed}")
        return v

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

    @field_validator("start_range", "end_range", mode="before")
    @classmethod
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
        "1h", description="Frequency of the meteorological data"
    )
    pull_nldas2: Optional[bool] = Field(
        False,
        description="Whether to pull the NLDAS2 files from the internet if dates missing from met station",
    )
    interp_method: Optional[str] = Field(
        "time", description="Interpolation method for missing data"
    )
    metstation_freq: Optional[str] = Field(
        # https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#timeseries-offset-aliases
        "5T",
        description="Frequency of the met station data",
    )

    @model_validator(mode="before")
    @classmethod
    def fill_optional(cls, values: dict[str, Any]) -> dict[str, Any]:
        incoming = dict(values or {})
        if not incoming:
            logger.info("No optional parameters specified, using defaults")
            incoming = dict(default_optional_met)

        # apply defaults for any missing keys
        for k, v in default_optional_met.items():
            if k not in incoming:
                logger.debug(f"Parameter {k} missing; using default")
                incoming[k] = v

        logger.debug(f"Optional parameters: {incoming}")
        return incoming


class ParametersConfig(BaseModel):

    parameters: Optional[Parameters] = Field(
        None, description="Dictionary of parameters to pull from which model"
    )


class MetforceConfig(BaseModel):
    """Metforce configuration class"""

    required: RequiredConfig
    optional: OptionalConfig
    parameters: ParametersConfig
    wind: WindConfig = Field(default_factory=WindConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @model_validator(mode="before")
    @classmethod
    def fill_in_default_met(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        vals = dict(values or {})
        parameters = vals.get("parameters")
        metfile = (vals.get("optional") or {}).get("metfile") if vals.get("optional") else None

        # If no parameters but metfile provided -> default met (station)
        if parameters is None and metfile:
            logger.info("No parameters specified, using default met parameters")
            vals["parameters"] = default_met
            parameters = vals["parameters"]

        # If neither parameters nor metfile -> GRIB/NLDAS defaults
        if parameters is None and metfile is None:
            logger.info("No parameters specified and no metfile; using NLDAS2 defaults")
            vals["parameters"] = default_met_grib
            parameters = vals["parameters"]

        # Fill missing parameter entries
        for p in list(default_met.keys()):
            if p not in parameters:
                logger.debug(f"Parameter {p} missing; using default")
                parameters[p] = default_met[p]

        # Fill per-parameter source/key/fraction defaults
        for param, settings in parameters.items():
            source = settings.get("source")
            if source is None:
                settings["source"] = default_met_sources[param]
            if settings["source"] == "met" and not settings.get("key"):
                settings["key"] = default_met_keys[param]
            if source == "global_fraction" and not settings.get("fraction"):
                settings["fraction"] = default_global_fraction[param]["fraction"]
            if source == "global_coszenith" and param == "direct_shortwave" and not settings.get("fraction"):
                settings["fraction"] = default_global_coszenith[param]["fraction"]
            parameters[param] = settings

        # Ensure nesting matches ParametersConfig shape
        vals["parameters"] = {"parameters": parameters}
        return vals


def parse_config(file_path: str) -> MetforceConfig:
    """Parse the configuration file"""
    logger.info(f"Parsing configuration file at {file_path}")
    try:
        config = toml.load(file_path)
        return MetforceConfig(**config)
    except Exception as e:
        logger.error(f"Error parsing configuration file: {e}")
        raise e
