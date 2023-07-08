from datetime import datetime
from typing import Any, Dict

import pandas as pd
from pydantic import BaseModel

from metforce.config import MetforceConfig

Parameters = Dict[str, Dict[str, Any]]
class ProcessDataParams(BaseModel):
    parameters: Parameters
    date_range: pd.DatetimeIndex
    latitude: float
    longitude: float
    elevation: float = 0.0
    tmp_grib_folder: str = "~/tmp_grib_folder"
    pull_grib: bool = False
    cleanup_folder: bool = False
    interp_method: str = "time"
    metfile: str = None
    metstation_freq: str = "5T"
    location_name: str = None

    class Config:
        arbitrary_types_allowed = True


class ProcessDataParamsBuilder:
    def __init__(self, parameters: Parameters, date_range: pd.DatetimeIndex, latitude: float, longitude: float):
        self.params = ProcessDataParams(parameters=parameters, date_range=date_range, latitude=latitude,
                                        longitude=longitude)

    def set_parameters(self, parameters: Dict[str, Dict[str, str]]):
        self.params.parameters = parameters
        return self

    def set_date_range(self, start_range: str, end_range: str, freq: str):
        self.params.date_range = pd.date_range(start=datetime.strptime(start_range, "%Y-%m-%d %H:%M"),
                                               end=datetime.strptime(end_range, "%Y-%m-%d %H:%M"),
                                               freq=freq)
        return self

    def set_latitude(self, latitude: float):
        self.params.latitude = latitude
        return self

    def set_longitude(self, longitude: float):
        self.params.longitude = longitude
        return self

    def set_elevation(self, elevation: float):
        self.params.elevation = elevation
        return self

    def set_tmp_grib_folder(self, tmp_grib_folder: str):
        self.params.tmp_grib_folder = tmp_grib_folder
        return self

    def set_pull_grib(self, pull_grib: bool):
        self.params.pull_grib = pull_grib
        return self

    def set_cleanup_folder(self, cleanup_folder: bool):
        self.params.cleanup_folder = cleanup_folder
        return self

    def set_interp_method(self, interp_method: str):
        self.params.interp_method = interp_method
        return self

    def set_metfile(self, metfile: str):
        self.params.metfile = metfile if metfile else None
        return self

    def set_metstation_freq(self, metstation_freq: str):
        self.params.metstation_freq = metstation_freq
        return self

    def set_location_name(self, location_name: str):
        self.params.location_name = location_name
        return self

    def build(self) -> ProcessDataParams:
        return self.params


def build_params(config: MetforceConfig) -> ProcessDataParams:
    # Assuming that date_range can be computed here
    date_range = pd.date_range(start=datetime.strptime(config.required.start_range, "%Y-%m-%d %H:%M"),
                               end=datetime.strptime(config.required.end_range, "%Y-%m-%d %H:%M"),
                               freq=config.optional.freq)

    builder = ProcessDataParamsBuilder(config.parameters.parameters,
                                       date_range,
                                       config.required.latitude,
                                       config.required.longitude)

    builder.set_tmp_grib_folder(config.optional.tmp_grib_folder) \
        .set_elevation(config.required.elevation) \
        .set_pull_grib(config.optional.pull_grib) \
        .set_cleanup_folder(config.optional.cleanup_folder) \
        .set_interp_method(config.optional.interp_method) \
        .set_metfile(config.optional.metfile) \
        .set_metstation_freq(config.optional.metstation_freq) \
        .set_location_name(config.optional.location_name)

    return builder.build()
