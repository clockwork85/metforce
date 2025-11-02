from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from metforce.data_types import Parameters
from metforce.logger_config import logger
from metforce.physics.dew_point import dewpoint_from_t_rh
from metforce.physics.solar_irradiance import decompose_shortwave

def process_global_fraction(global_shortwave: pd.Series, fraction: float) -> pd.Series:
    return global_shortwave * fraction


def process_coszenith(global_shortwave: pd.Series, zenith: float, fraction: float) -> Dict[str, pd.Series]:
    direct_shortwave = global_shortwave * fraction * np.cos(np.radians(zenith))
    diffuse_shortwave = global_shortwave - direct_shortwave
    return {'direct_shortwave': direct_shortwave, 'diffuse_shortwave': diffuse_shortwave}

# Function for Global data processing
def process_global_data(
        parameters: Parameters,
        date_range: pd.DatetimeIndex,
        dataframes: dict[str, pd.DataFrame],
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        elevation: float | None = None,
) -> Optional[pd.DataFrame]:
    """
    Create a DataFrame with any *derived* short‑wave columns requested
    in the configuration.

    Supported *source*= strings (for ``direct_shortwave`` / ``diffuse_shortwave``):

    * ``global_fraction`` – constant fraction of GHI.                           
    * ``global_coszenith`` – fraction·cos(zenith).                          
    * ``pvlib_disc``     – pvlib.irradiance.disc                           
    * ``pvlib_dirint``   – pvlib.irradiance.dirint                        
    * ``pvlib_dirindex`` – pvlib.irradiance.dirindex                     
    * ``pvlib_erbs``     – pvlib.irradiance.erbs                        

    These models run on the curve of the GHI, so we need to run on the entire 
    pd.Series to get sensical DNI
    """
    global_parameters = [
            key for key in parameters 
            if parameters[key]['source'].startswith(('global', 'pvlib_'))
    ]
    if not global_parameters:
        return None

    logger.debug(f"Derived shortwave parameters requested: {global_parameters=}")

    # Grab the base GHI series
    shortwave_src = parameters["global_shortwave"]["source"]
    ghi = dataframes[shortwave_src]["global_shortwave"].clip(lower=0.0)
    logger.debug(f"GHI source {shortwave_src!r} with {ghi.size} points")

    # Pre-fetch zenith if any pvlib method is present
    needs_pvlib = any(
            parameters[p]["source"].startswith("pvlib") for p in global_parameters
    )
    if needs_pvlib: 
        zenith_src = parameters["zenith"]["source"]
        zenith = dataframes[zenith_src]["zenith"]
        logger.debug(f"Using zenith from {zenith_src!r}")
        temp_dew = None
        if "temperature" in parameters and "relative_humidity" in parameters:
            t_src = parameters["temperature"]["source"]
            rh_src = parameters["relative_humidity"]["source"]
            if t_src in dataframes and rh_src in dataframes:
                temp_dew = dewpoint_from_t_rh(
                    dataframes[t_src]["temperature"]["source"],
                    dataframes[rh_src]["relative_humidity"]["source"]
                )

    derived: dict[str, pd.Series] = {}

    # Per parameter dispatch 
    for param in global_parameters:
        src = parameters[param]["source"]

        # Case 1: percentage-based split -> interpret as BHI fraction, then convert to DNI
        # pretty much never use this anymore except for testing
        if src == "global_fraction" or (src.startswith("global_") and src.endswith("%")):
            if param == "direct_shortwave":
                # choose fraction
                if src == "global_fraction":
                    fraction = parameters[param]["fraction"]
                else:
                    fraction = float(src.split("_")[1][:-1]) / 100.0

                # need zenith to go from BHI to DNI
                zenith = dataframes[parameters["zenith"]["source"]]["zenith"]
                ghi_aligned, zenith_aligned = ghi.align(zenith, join="inner")
                cosz = np.cos(np.radians(zenith_aligned.clip(upper=90.0))).clip(min=0.0)

                # BHI = f * GHI; DNI = BHI / cosz (with safe handling at night)
                bhi = (fraction * ghi_aligned).clip(lower=0.0)
                dni = (bhi.where(cosz > 0.0, 0.0) / cosz.where(cosz > 0.0, 1.0)).clip(lower=0.0)
                dhi = (ghi_aligned - bhi).clip(lower=0.0)

                derived.update({
                    "direct_shortwave": dni.reindex(date_range),
                    "diffuse_shortwave": dhi.reindex(date_range),
                })

        # Case 2: fraction * cos(zenith) model — that gives BHI by construction; convert to DNI
        # Pretty much never use this anymore except for testing - prefer PVLIB
        elif src == "global_coszenith":
            if param == "direct_shortwave":
                zenith = dataframes[parameters["zenith"]["source"]]["zenith"]
                fraction = parameters[param]["fraction"]

                ghi_aligned, zenith_aligned = ghi.align(zenith, join="inner")
                cosz = np.cos(np.radians(zenith_aligned.clip(upper=90.0))).clip(min=0.0)

                bhi = (ghi_aligned * fraction * cosz).clip(lower=0.0)
                dni = (bhi.where(cosz > 0.0, 0.0) / cosz.where(cosz > 0.0, 1.0)).clip(
                    lower=0.0
                )
                dhi = (ghi_aligned - bhi).clip(lower=0.0)

                derived.update(
                    {
                        "direct_shortwave": dni.reindex(date_range),
                        "diffuse_shortwave": dhi.reindex(date_range),
                    }
                )

        # Case 3 - pvlib-based physical models 
        elif src.startswith("pvlib_"):
            method = src.split("_", 1)[1]  # disc|dirint|dirindex|erbs
            if "direct_shortwave" not in derived or "diffuse_shortwave" not in derived:
                press_key = parameters["pressure"].get("key") or "BP_mbar"
                pressure_pa = None
                df_met = dataframes.get("MET") or dataframes.get("met")
                if df_met is not None and press_key in df_met:
                    pressure_pa = 100.0 * df_met[press_key].astype(float)
                out = decompose_shortwave(
                    ghi=ghi, zenith=zenith, method=method,
                    latitude=latitude, longitude=longitude, elevation_m=elevation,
                    pressure_pa=pressure_pa,
                    temp_c=dataframes.get("Temp"),
                    rh_percent=dataframes.get("RH"),
                    use_delta_kt_prime=True,
                )
                derived.update(out)
            break
        else:
            raise ValueError(f"Unknown source specifier {src!r} for {param}")

    global_df = pd.DataFrame(derived, index=date_range)
    logger.info(
            f"Built global shortwave dataframe with columns {list(global_df.columns)}"
    )

    parameters["direct_shortwave"]["source"] = "global"
    parameters["diffuse_shortwave"]["source"] = "global"

    return global_df


def build_global_df(
        global_parameters: Dict[str, float],
        date_range: pd.DatetimeIndex,
        global_shortwave: pd.Series
) -> pd.DataFrame:

    logger.trace(f"From build_global_df: {global_parameters=}")
    logger.trace(f"Global shortwave: {global_shortwave=}")
    global_dict = {}
    for parameter, fraction in global_parameters.items():
        global_dict[parameter] = global_shortwave * fraction

    if len(global_dict) != len(global_parameters):
        missing_parameters = set(global_parameters) - set(global_dict.keys())
        raise KeyError(f"The following parameters are not supported by any pvlib functions: {missing_parameters}")
    logger.info(f"Global dataframe built with parameters: {', '.join(list(global_dict.keys())).rstrip(', ')}")
    return pd.DataFrame(global_dict, index=date_range)

# Helper function to modify global parameters
def modify_global_parameters(global_parameters: List[str], parameters: Parameters) -> Dict[str, float]:
    global_parameters_dict = {}
    for key in global_parameters:
        if parameters[key]['source'].startswith('global'):
            fraction = float(parameters[key]['source'].split('_')[1][:-1]) / 100.0
            parameters[key]['source'] = 'global'
            global_parameters_dict[key] = fraction
    logger.trace(f"{global_parameters_dict=}")
    return global_parameters_dict

def build_brunt_df(
        brunt_parameters: List[str],
        date_range: pd.DatetimeIndex,
        temperature: pd.Series,
        relative_humidity: pd.Series
) -> pd.DataFrame:

    logger.trace(f"From build_brunt_df: {brunt_parameters=}")
    logger.trace(f"{temperature=}")
    logger.trace(f"{relative_humidity=}")
    brunt_dict = {}
    for parameter in brunt_parameters:
        brunt_dict[parameter] = calculate_dlr_brunt(temperature, relative_humidity)

    if len(brunt_dict) != len(brunt_parameters):
        missing_parameters = set(brunt_parameters) - set(brunt_dict.keys())
        raise KeyError(f"The following parameters are not supported by any pvlib functions: {missing_parameters}")
    logger.info(f"Global dataframe built with parameters: {', '.join(list(brunt_dict.keys())).rstrip(', ')}")
    return pd.DataFrame(brunt_dict, index=date_range)



def process_brunt_data(parameters: Parameters, date_range: pd.DatetimeIndex,
                        dataframes: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
    brunt_parameters = [key for key in parameters.keys() if parameters[key]['source'].startswith('brunt')]
    logger.trace(f"{brunt_parameters=}")

    if brunt_parameters:
        # brunt_parameters = modify_brunt_parameters(brunt_parameters, parameters)
        temp_source = parameters['temperature']['source']
        temperature = dataframes[temp_source]['temperature']
        relative_humidity_source = parameters['relative_humidity']['source']
        relative_humidity = dataframes[relative_humidity_source]['relative_humidity']
        brunt_df = build_brunt_df(brunt_parameters, date_range, temperature, relative_humidity)
    else:
        brunt_df = None
    return brunt_df


def calculate_dlr_brunt(temp_celsius: pd.Series, relative_humidity: pd.Series) -> pd.Series:
    """
    Calculates downwelling longwave radiation (DLR) using the Brunt equation.

    Parameters
    ----------
    temp_celsius : pd.Series
        Temperature in Celsius.
    relative_humidity : pd.Series
        Relative humidity in percentage (0 to 100).

    Returns
    -------
    pd.Series
        Downwelling longwave radiation in W/m^2.
    """
    stefan_boltzmann_constant = 5.67e-8
    temp_kelvin = temp_celsius + 273.15
    saturation_vapor_pressure = 6.11 * np.exp(5420 * (1/273.15 - 1/temp_kelvin))
    vapor_pressure = saturation_vapor_pressure * relative_humidity / 100
    emissivity = 0.785 - 0.00246 * temp_kelvin + 0.0000129 * temp_kelvin**2
    effective_emissivity = emissivity + 0.0224 * np.sqrt(vapor_pressure)
    return effective_emissivity * stefan_boltzmann_constant * temp_kelvin**4