from collections import OrderedDict

default_optional_met = {
    "outfile": "test.met",
    "metfile": None,
    "header": None,
    "tmp_grib_folder": "~/tmp_grib_folder",
    "cleanup_folder": False,
    "freq": "1H",
    "pull_grib": True,
    "interp_method": "time",
}

default_met = {
    "pressure": {},
    "temperature": {},
    "relative_humidity": {},
    "wind_speed": {},
    "wind_direction": {},
    "precipitation": {},
    "global_shortwave": {},
    "diffuse_shortwave": {},
    "direct_shortwave": {},
    "downwelling_lwir": {},
    "zenith": {},
    "azimuth": {},
}

default_met_grib = {
    "pressure": {"source": "grib"},
    "temperature": {"source": "grib"},
    "relative_humidity": {"source": "grib"},
    "wind_speed": {"source": "grib"},
    "wind_direction": {"source": "grib"},
    "precipitation": {"source": "grib"},
    "global_shortwave": {"source": "grib"},
    "diffuse_shortwave": {"source": "global_20%"},
    "direct_shortwave": {"source": "global_80%"},
    "downwelling_lwir": {"source": "grib"},
    "zenith": {"source": "pvlib"},
    "azimuth": {"source": "pvlib"},
}

default_met_keys = {
    "pressure": "BP_mbar",
    "temperature": "AirT_2M",
    "relative_humidity": "RH_2M",
    "wind_speed": "Wind_Spd_2M",
    "wind_direction": "Wind_Dir_2M",
    "precipitation": "Precip_Tot",
    "global_shortwave": "PSP_Total",
    "diffuse_shortwave": "Diffuse",
    "direct_shortwave": "Direct",
    "downwelling_lwir": "PIR_Flux",
    "zenith": "ZenDeg",
    "azimuth": "AzDeg",
}

default_met_sources = {
    "pressure": "met",
    "temperature": "met",
    "relative_humidity": "met",
    "wind_speed": "met",
    "wind_direction": "met",
    "precipitation": "met",
    "global_shortwave": "met",
    "diffuse_shortwave": "global_20%",
    "direct_shortwave": "global_80%",
    "downwelling_lwir": "met",
    "zenith": "pvlib",
    "azimuth": "pvlib",
    "visibility": "-",
    "aerosol": "-",
    "cloud_cover_1": "-",
    "cloud_cover_2": "-",
    "cloud_cover_3": "-",
    "cloud_cover_4": "-",
    "cloud_cover_5": "-",
    "cloud_cover_6": "-",
    "cloud_cover_7": "-",
}

default_met_decimal = {
    "pressure": 1,
    "temperature": 2,
    "relative_humidity": 1,
    "wind_speed": 1,
    "wind_direction": 1,
    "precipitation": 2,
    "global_shortwave": 2,
    "diffuse_shortwave": 2,
    "direct_shortwave": 2,
    "downwelling_lwir": 2,
    "zenith": 1,
    "azimuth": 1,
}

default_met_width = {
    "day": 5,
    "hour": 3,
    "minute": 4,
    "pressure": 7,
    "temperature": 7,
    "relative_humidity": 6,
    "wind_speed": 8,
    "wind_direction": 8,
    "visibility": 5,
    "aerosol": 5,
    "cloud_cover_1": 4,
    "cloud_cover_2": 4,
    "cloud_cover_3": 4,
    "cloud_cover_4": 4,
    "cloud_cover_5": 4,
    "cloud_cover_6": 4,
    "cloud_cover_7": 4,
    "precipitation": 7,
    "global_shortwave": 7,
    "diffuse_shortwave": 9,
    "direct_shortwave": 7,
    "downwelling_lwir": 8,
    "zenith": 7,
    "azimuth": 7,
}

default_met_units = OrderedDict()
default_met_units["day"] = "j"
default_met_units["hour"] = "-"
default_met_units["minute"] = "-"
default_met_units["pressure"] = "mbar"
default_met_units["temperature"] = "degC"
default_met_units["relative_humidity"] = "%"
default_met_units["wind_speed"] = "m/s"
default_met_units["wind_direction"] = "deg"
default_met_units["visibility"] = "m"
default_met_units["aerosol"] = "m"
default_met_units["cloud_cover_1"] = "-"
default_met_units["cloud_cover_2"] = "-"
default_met_units["cloud_cover_3"] = "-"
default_met_units["cloud_cover_4"] = "-"
default_met_units["cloud_cover_5"] = "-"
default_met_units["cloud_cover_6"] = "-"
default_met_units["cloud_cover_7"] = "-"
default_met_units["precipitation"] = "mm"
default_met_units["global_shortwave"] = "W/m2"
default_met_units["direct_shortwave"] = "W/m2"
default_met_units["diffuse_shortwave"] = "W/m2"
default_met_units["downwelling_lwir"] = "W/m2"
default_met_units["zenith"] = "deg"
default_met_units["azimuth"] = "deg"

default_col_names = OrderedDict()
default_col_names["day"] = "Day"
default_col_names["hour"] = "Hr"
default_col_names["minute"] = "Min"
default_col_names["pressure"] = "Press"
default_col_names["temperature"] = "Temp"
default_col_names["relative_humidity"] = "RH"
default_col_names["wind_speed"] = "WndSpd"
default_col_names["wind_direction"] = "WndDir"
default_col_names["visibility"] = "Vis"
default_col_names["aerosol"] = "Aer"
default_col_names["precipitation"] = "Precip"
default_col_names["cloud_cover_1"] = "CC1"
default_col_names["cloud_cover_2"] = "CC2"
default_col_names["cloud_cover_3"] = "CC3"
default_col_names["cloud_cover_4"] = "CC4"
default_col_names["cloud_cover_5"] = "CC5"
default_col_names["cloud_cover_6"] = "CC6"
default_col_names["cloud_cover_7"] = "CC7"
default_col_names["global_shortwave"] = "Global"
default_col_names["direct_shortwave"] = "Direct"
default_col_names["diffuse_shortwave"] = "Diffuse"
default_col_names["downwelling_lwir"] = "LWdwn"
default_col_names["zenith"] = "Zenith"
default_col_names["azimuth"] = "Azimuth"

