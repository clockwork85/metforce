## Configuration

Configuration of MetForce is done through a `toml` file. Below is a description of how to set it up:

### Required Parameters

This section sets up basic geographic and time information. All fields are required.

- `latitude` : Latitude of the location in degrees.
- `longitude` : Longitude of the location in degrees.
- `elevation` : Elevation of the location in meters.
- `start_range` : The start date and time for the data range (in UTC).
- `end_range` : The end date and time for the data range (in UTC).

```toml
[required]
latitude = 39.1
longitude = -98.3
elevation = 450
start_range = "2020-01-27 00:00"
end_range = "2020-01-27 06:00"
```

### Optional Parameters

This section sets up additional optional information.

- `outfile` : Name of the output file. Default is `test.met`.
- `metfile` : Path to the input meteorological station data file. No default value.
- `metstation_freq` : Desired frequency of the meteorological data. Uses [pandas offset aliases](https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#timeseries-offset-aliases). No default value.
- `location_name` : Name of the location. No default value.
- `tmp_grib_folder` : Path to store temporary grib files. Default is `~/tmp_grib_folder`.
- `cleanup_folder` : If `true`, the temporary grib files are deleted after usage. Default is `false`.
- `freq` : Desired frequency of the output data. Default is `1H`.
- `pull_grib` : If `true`, the grib data is pulled automatically. Default is `true`.
- `interp_method` : Desired method for interpolation. Default is `time`. You can use any of the [pandas interpolation methods](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.interpolate.html#pandas.DataFrame.interpolate).

```toml
[optional]
outfile = "test.met"
metfile = "data/Yuma_Testing.xlsx"
metstation_freq = "5T"
location_name = "Yuma Providing Grounds"
tmp_grib_folder = "~/tmp_grib_folder"
cleanup_folder = false
freq = "1H"
pull_grib = true
interp_method = "time"
```

### Parameters Configuration
This section configures the data sources for each parameter.

Each parameter has a `source` option that can be set to `grib`, `met`, `pvlib`, `derived` a function of another column (i.e. global_80%, global_20%), or a custom source.

Each parameter also has an optional `key` option which can be used to override the default column name.

```toml
[parameters.pressure]
source = "met"

[parameters.temperature]
source = "grib"
```

## Default Settings

If an optional argument is not provided, these are the defaults:

| Parameter       | Default             |
|-----------------|---------------------|
| outfile         | "test.met"          |
| metfile         | None                |
| header          | None                |
| tmp_grib_folder | "~/tmp_grib_folder" |
| cleanup_folder  | False               |
| freq            | "1H"                |
| pull_grib       | True                |
| interp_method   | "time"              |

These are the default data sources for each parameter if you leave something under parameters blank:

| Parameter         | Default Source |
|-------------------|----------------|
| pressure          | "met"          |
| temperature       | "met"          |
| relative_humidity | "met"          |
| wind_speed        | "met"          |
| wind_direction    | "met"          |
| precipitation     | "met"          |
| global_shortwave  | "met"          |
| diffuse_shortwave | "global_20%"   |
| direct_shortwave  | "global_80%"   |
| downwelling_lwir  | "met"          |
| zenith            | "pvlib"        |
| azimuth           | "pvlib"        |

This is the default NLDAS GRIB configuration:

| Parameter         | Source       |
|-------------------|--------------|
| pressure          | "grib"       |
| temperature       | "grib"       |
| relative_humidity | "grib"       |
| wind_speed        | "grib"       |
| wind_direction    | "grib"       |
| precipitation     | "grib"       |
| global_shortwave  | "grib"       |
| diffuse_shortwave | "global_20%" |
| direct_shortwave  | "global_80%" |
| downwelling_lwir  | "grib"       |
| zenith            | "pvlib"      |
| azimuth           | "pvlib"      |