from datetime import datetime
import pandas as pd
import numpy as np

from metforce import (
    check_for_missing_dates,
    fill_in_missing_metdata,
    get_solar_positions,
)


def test_albuquerque():
    latitude = 35.0844
    longitude = -106.6504
    year = 2023
    julian_day = 152

    hour = 18
    minute = 0

    zenith, azimuth = get_solar_positions(
        year, julian_day, hour, minute, latitude, longitude
    )
    assert np.isclose(zenith[0], 19.22, atol=1)
    assert np.isclose(azimuth[0], 128.68, atol=1)

    hour = 12
    minute = 0
    zenith, azimuth = get_solar_positions(
        year, julian_day, hour, minute, latitude, longitude
    )
    assert np.isclose(zenith[0], 89.72, atol=1)
    assert np.isclose(azimuth[0], 62.99, atol=1)

    hour = 6
    minute = 30
    zenith, azimuth = get_solar_positions(
        year, julian_day, hour, minute, latitude, longitude
    )
    assert np.isclose(zenith[0], 122.35, atol=1)
    assert np.isclose(azimuth[0], 350.57, atol=1)


def test_new_york():
    latitude = 40.7128
    longitude = -74.0060
    year = 2023
    julian_day = 152

    hour = 16
    minute = 0

    zenith, azimuth = get_solar_positions(
        year, julian_day, hour, minute, latitude, longitude
    )
    assert np.isclose(zenith[0], 21.9, atol=1)
    assert np.isclose(azimuth[0], 144.72, atol=1)

    hour = 10
    minute = 0
    zenith, azimuth = get_solar_positions(
        year, julian_day, hour, minute, latitude, longitude
    )
    assert np.isclose(zenith[0], 85.36, atol=1)
    assert np.isclose(azimuth[0], 64.8, atol=1)

    hour = 4
    minute = 30
    zenith, azimuth = get_solar_positions(
        year, julian_day, hour, minute, latitude, longitude
    )
    assert np.isclose(zenith[0], 117.2, atol=1)
    assert np.isclose(azimuth[0], 353.84, atol=1)


def test_check_for_missing_dates_no_missing_hourly():
    dates = pd.date_range("2023-01-01", "2023-01-02", freq="H")
    df = pd.DataFrame(range(len(dates)), index=dates)

    missing_dates = check_for_missing_dates(df, dates)

    assert len(missing_dates) == 0, "No dates should be missing"


def test_check_for_missing_dates_some_missing_hourly():
    full_dates = pd.date_range("2023-01-01", "2023-01-02", freq="H")
    missing_dates = pd.date_range("2023-01-01 12:00", "2023-01-01 14:00", freq="H")
    incomplete_dates = full_dates.difference(missing_dates)

    df = pd.DataFrame(range(len(incomplete_dates)), index=incomplete_dates)

    missing_dates_found = check_for_missing_dates(df, full_dates)

    assert set(missing_dates_found) == set(
        missing_dates
    ), "All missing dates should be found"


def test_check_for_missing_dates_all_missing_hourly():
    full_dates = pd.date_range("2023-01-01", "2023-01-02", freq="H")
    df = pd.DataFrame()  # Empty DataFrame

    missing_dates_found = check_for_missing_dates(df, full_dates)

    assert set(missing_dates_found) == set(
        full_dates
    ), "All dates should be found to be missing"


def test_fill_in_missing_metdata_resampling():
    # Create sample metdata DataFrame
    metdata = pd.DataFrame(
        {
            "precipitation": [0.1] * 4 + [0.2] * 4 + [0] * 4 + [0.4] * 4,
            "temperature": [
                20,
                np.nan,
                20,
                21,
                22,
                np.nan,
                22,
                21,
                23,
                24,
                np.nan,
                24,
                25,
                26,
                np.nan,
                26,
            ],
        },
        index=pd.date_range(start="2023-01-01", periods=16, freq="15T"),
    )

    met_key = {"precipitation": "precipitation", "temperature": "temperature"}
    date_range = pd.date_range(start="2023-01-01", periods=4, freq="H")

    # Call function
    result = fill_in_missing_metdata(metdata, met_key, date_range, "15T", "linear")

    # Check the precipitation values
    assert np.allclose(result["precipitation"].values, [0.4, 0.8, 0.0, 1.6], atol=1e-5)

    # Check the temperature values
    expected_temp = [20.25, 21.75, 23.75, 25.75]
    assert np.allclose(result["temperature"].values, expected_temp, atol=1e-5)


def test_fill_in_missing_metdata_interpolation():
    # Create sample metdata DataFrame with some missing values
    metdata = pd.DataFrame(
        {
            "precipitation": [0.1, np.nan, 0.8, 0],
            "temperature": [20, 21, np.nan, 23],
        },
        index=pd.date_range(start="2023-01-01", periods=4, freq="H"),
    )

    met_key = {"precipitation": "precipitation", "temperature": "temperature"}
    date_range = pd.date_range(start="2023-01-01", periods=4, freq="H")

    # Call function
    result = fill_in_missing_metdata(metdata, met_key, date_range, "H", "linear")

    # Check the precipitation values
    assert np.allclose(result["precipitation"].values, [0.1, 0.45, 0.8, 0], atol=1e-5)

    # Check the temperature values
    expected_temp = [20, 21, 22, 23]
    assert np.allclose(result["temperature"].values, expected_temp, atol=1e-5)
