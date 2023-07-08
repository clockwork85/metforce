from abc import ABC
from enum import Enum
from typing import Any, Callable, Dict

from processing import process_grib_data, process_met_station_data, process_pvlib_data, process_global_data

Parameters = Dict[str, Dict[str, Any]]

class DataSourceStrategy(ABC):
    def __init__(self, processing_function: Callable):
        self.processing_function = processing_function

    def process_data(self, parameters: Parameters, **kwargs):
        return self.processing_function(parameters, **kwargs)


class GribDataSourceStrategy(DataSourceStrategy):

    def __init__(self):
        super().__init__(process_grib_data)


class MetDataSourceStrategy(DataSourceStrategy):

    def __init__(self):
        super().__init__(process_met_station_data)


class PvlibDataSourceStrategy(DataSourceStrategy):
    def __init__(self):
        super().__init__(process_pvlib_data)


class GlobalDataSourceStrategy(DataSourceStrategy):
    def __init__(self):
        super().__init__(process_global_data)


class Source(Enum):
    GRIB = "grib"
    MET = "met"
    PVLIB = "pvlib"
    GLOBAL = "global"


source_strategies = {
    Source.GRIB.value: GribDataSourceStrategy(),
    Source.MET.value: MetDataSourceStrategy(),
    Source.PVLIB.value: PvlibDataSourceStrategy(),
    Source.GLOBAL.value: GlobalDataSourceStrategy(),
}
