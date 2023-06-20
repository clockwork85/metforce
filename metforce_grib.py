from enum import Enum
import datetime
from http.cookiejar import CookieJar
from pathlib import Path
import shutil
from typing import Dict, List
import urllib

import eccodes
from loguru import logger
import pandas as pd


def get_pressure_grib(gid_list: List, latitude: float, longitude: float) -> float:
    gid = gid_list[GID.SURFACE_PRESSURE.value]
    nearest = eccodes.codes_grib_find_nearest(gid, latitude, longitude)[0]
    pressure_in_Pa = nearest.value
    pressure_in_kPa = pressure_in_Pa / 1000.0
    return pressure_in_kPa


def get_temperature_grib(gid_list: List, latitude: float, longitude: float) -> float:
    gid = gid_list[GID.TMP_2M_ABOVE_GROUND_TEMPERATURE.value]
    nearest = eccodes.codes_grib_find_nearest(gid, latitude, longitude)[0]
    temperature_in_K = nearest.value
    temperature_in_C = temperature_in_K - 273.15
    return temperature_in_C


def get_relative_humidity_grib(
    gid_list: List, latitude: float, longitude: float
) -> float:
    # gid = gid_list[GID.ABOVE_GROUND_SPECIFIC_HUMIDITY.value]
    # nearest = eccodes.codes_grib_find_nearest(gid, latitude, longitude)[0]
    # relative_humidity = nearest.value
    return 0.10


grib_function_mapper = {
    "pressure": get_pressure_grib,
    "temperature": get_temperature_grib,
    "relative_humidity": get_relative_humidity_grib,
}


class GID(Enum):
    TMP_2M_ABOVE_GROUND_TEMPERATURE = 0
    ABOVE_GROUND_SPECIFIC_HUMIDITY = 1
    SURFACE_PRESSURE = 2
    ABOVE_GROUND_ZONAL_WIND_SPEED = 3
    ABOVE_GROUND_MERIDIONAL_WIND_SPEED = 4
    LW_RADIATION_FLUX_DOWNWARDS = 5
    FRACTION_OF_TOTAL_PRECIPITATION_CONV = 6
    POTENTIAL_ENERGY = 7
    POTENTIAL_EVAPORATION = 8
    PRECIPITATION_HOURLY_TOTAL = 9
    SW_RADIATION_FLUX_DOWNWARDS = 10


def retrieve_gid_list(gribfile: str) -> List:
    # with statement guarantees that an fid.close() is performed
    with open(gribfile, "rb") as fid:

        # Get number of data layers from GRIB file (known as messages)
        try:
            message_count = eccodes.codes_count_in_file(fid)
        except Exception as e:
            # This is when there is an incomplete file in your list - So it
            # will attempt to delete and redownload it
            logger.error(f"Error in {gribfile} - {e}")
            raise e
        # Get a pointer list to each data layer
        gid_list = [eccodes.codes_grib_new_from_file(fid) for i in range(message_count)]

    return gid_list


def build_grib_df(
    parameters: List[str],
    grib_dates_and_files: Dict[datetime.datetime, str],
    latitude: float,
    longitude: float,
) -> pd.DataFrame:
    """
    Builds a dataframe of grib data for a given list of parameters and dates
    """
    try:
        grib_dates = sorted(grib_dates_and_files.keys())
        parameter_series_dict = {
            parameter: pd.Series(
                [
                    grib_function_mapper[parameter](
                        retrieve_gid_list(grib_dates_and_files[date]),
                        latitude,
                        longitude,
                    )
                    for date in grib_dates
                ],
                index=grib_dates,
            )
            for parameter in parameters
            if parameter in grib_function_mapper
        }
        if len(parameter_series_dict) != len(parameters):
            missing_parameters = set(parameters) - set(parameter_series_dict.keys())
            raise KeyError(
                f"The following parameters are not available in GRIB LDAS data: {missing_parameters}"
            )
        grib_df = pd.DataFrame(parameter_series_dict)
        return grib_df
    except Exception as e:
        logger.error(f"Error building grib dataframe: {e}")
        raise e


def write_grib_file_to_path(date, header, gribfile, tmp_grib_folder):
    """
    Grabs a grib file from the NASA website
    """
    # Grabbing the grib file
    tmp_grib_folder = Path(tmp_grib_folder).expanduser()
    gribfilepath = tmp_grib_folder / gribfile
    logger.debug(f"Writing grib file to {gribfilepath}")
    lp = open(gribfilepath, "wb")
    logger.info(f"Retrieving grib file {gribfile} from NASA NLDAS for {date}")

    # Getting into the proper directory
    yr = str(date.year)  # Year directory
    day = str("%03d" % date.dayofyear)  # Day directory
    # filename = self.ftp.retrbinary('RETR ' + gribfile, lp.write)

    url = header + "/" + yr + "/" + day + "/" + gribfile
    request = urllib.request.Request(url)
    response = urllib.request.urlopen(request)

    lp.write(response.read())
    # self.ftp.cwd('../../') # Back to the main directory
    lp.close()


def pull_grib_files(
    grib_dates: List[datetime.datetime],
    latitude: float,
    longitude: float,
    tmp_grib_folder: str,
    cleanup_folder: bool = False,
) -> List[str]:
    grib_files_and_dates = {}
    try:
        for date in grib_dates:
            logger.debug(f"Pulling grib file for {date}")
            grib_files_and_dates[date] = pull_grib_file(
                date, latitude, longitude, tmp_grib_folder, cleanup_folder
            )
    except Exception as e:
        logger.error(f"Error pulling grib files: {e}")
        raise e
    finally:
        if cleanup_folder:
            logger.debug(f"Removing temporary grib folder {tmp_grib_folder}")
            shutil.rmtree(tmp_grib_folder)
        logger.success("Successfully pulled all grib files")

    return grib_files_and_dates


def pull_grib_file(
    date: datetime.datetime,
    latitude: float,
    longitude: float,
    tmp_grib_folder: str,
    cleanup_folder: bool = False,
) -> str:
    """
    Nasa FTP GRIB file reader - Pulls down a grib file locally using ftp
    and extracts the data into our met file format

    Full documentation can be found at:
    http://ldas.gsfc.nasa.gov/nldas/NLDAS2forcing.php

    Data Holding Listings can be found here:
    http://disc.sci.gsfc.nasa.gov/hydrology/data-holdings

    Actual data can be found here:
    ftp://hydro1.sci.gsfc.nasa.gov/data/s4pa/NLDAS/NLDAS_FORA0125_H.002/
    """

    # I believe these are static variables that do not change
    FTPURL = "https://hydro1.gesdisc.eosdis.nasa.gov/"
    FTPDIR = "data/NLDAS/NLDAS_FORA0125_H.002"
    header = FTPURL + FTPDIR

    gribfile = "NLDAS_FORA0125_H.A%d%02d%02d.%02d00.002.grb" % (
        date.year,
        date.month,
        date.day,
        date.hour,
    )

    user = "ERDC"
    passwd = "Erdc5437"

    password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, "https://urs.earthdata.nasa.gov", user, passwd)

    cookie_jar = CookieJar()

    opener = urllib.request.build_opener(
        urllib.request.HTTPBasicAuthHandler(password_manager),
        urllib.request.HTTPCookieProcessor(cookie_jar),
    )
    urllib.request.install_opener(opener)

    # Setting up directory and searching for local copy
    local_copy = find_local_grib_file(gribfile, tmp_grib_folder)
    if not local_copy:
        write_grib_file_to_path(date, header, gribfile, tmp_grib_folder)
    else:
        logger.debug(f"Found local copy of {gribfile} at for {date}")

    return str(Path(tmp_grib_folder).expanduser() / gribfile)

    # ======================================================================
    # FORCING message order for (NLDAS_FORA0125_H.A20140324.0800.002.grb)
    #  determined from grib_dump and *.grb.xml
    #
    # 0, TMP 2m above ground temperature
    # 1, 2-m above ground specific humidity (kg/kg)
    # 2, Surface pressure (Pa)
    # 3, 10-m above ground zonal wind speed (m/s)
    # 4, 10-m above ground meridional wind speed (m/s)
    # 5, LW radiation flux downwards (W/m^2)
    # 6, Fraction of total precipitation that is convective
    # 7, Potential energy (J/kg)
    # 8, Potential evaporation (kg/m^2)
    # 9, Precipitation hourly total (kg/m^2)
    # 10, SW radiation flux downards (W/m^2)
    # ======================================================================


def find_local_grib_file(gribfile: str, tmp: str) -> bool:
    """
    Setting up local folder and looking for a local copy of the file
    """

    tmp_path = Path(tmp).expanduser()
    if not tmp_path.exists():
        logger.debug(f"Creating temporary directory: {tmp_path}")
        tmp_path.mkdir(exist_ok=True)
    gribfile_path = tmp_path / gribfile

    logger.debug(
        f"Looking for local copy of {gribfile_path} and finding {gribfile_path.is_file()}"
    )
    return gribfile_path.is_file()
