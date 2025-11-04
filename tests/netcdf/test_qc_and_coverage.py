import numpy as np
import pandas as pd

from metforce.output import build_netcdf_dataset

def test_qc_flags_base_codes_and_missing():
    """Test quality assessment in Phase 3 (attributes, not arrays)."""
    # 3 timestamps hourly, with one NaN in temperature to exercise missing data
    idx = pd.date_range("2024-01-01 00:00", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "Press": [1013.0, 1012.5, 1012.0],
            "Temp": [20.0, np.nan, 21.0],
        },
        index=idx,
    )

    params = {
        "pressure": {"source": "met"},
        "temperature": {"source": "nldas2"},
    }

    ds = build_netcdf_dataset(df, meta={"title": "qc test"}, parameters=params)

    # Phase 3: Quality documented in attributes, not QC arrays
    # Pressure: complete data
    assert "quality_assessment" in ds["air_pressure"].attrs
    assert (
        ds["air_pressure"].attrs["quality_assessment"]
        == "All values consistent quality"
    )

    # Temperature: has missing data (1 NaN out of 3)
    assert "quality_assessment" in ds["air_temperature"].attrs
    assert "Data coverage:" in ds["air_temperature"].attrs["quality_assessment"]
    # Should be 66.7% coverage (2/3 valid)
    assert "66" in ds["air_temperature"].attrs["quality_assessment"]

    # Phase 3: No QC flag arrays created yet (deferred to Phase 5)
    assert "qc_flag_air_pressure" not in ds
    assert "qc_flag_air_temperature" not in ds

def test_coverage_ok_and_min_fraction():
    # 5 timestamps; RH missing in 2/5 -> coverage 0.6; pressure complete -> 1.0
    idx = pd.date_range("2024-01-01 00:00", periods=5, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "Press": [1013, 1012, 1011, 1010, 1010],
        "RH":    [50.0, np.nan, 40.0, np.nan, 35.0],  # 3/5 valid
    }, index=idx)

    params = {"pressure": {"source": "met"}, "relative_humidity": {"source": "met"}}
    ds = build_netcdf_dataset(df, meta={}, parameters=params)

    assert "coverage_min_fraction_core" in ds.attrs
    assert ds.attrs["coverage_ok"] == 0  # min fraction is 0.6 < 0.8
    assert 0.59 < ds.attrs["coverage_min_fraction_core"] < 0.61

def test_iso_time_and_day_of_year():
    idx = pd.date_range("2023-01-01 00:00", periods=2, freq="1h", tz="UTC")
    df = pd.DataFrame(index=idx)
    ds = build_netcdf_dataset(df, meta={})
    iso = ds["iso_time"].values.tolist()
    assert iso == ["2023-01-01T00:00:00Z", "2023-01-01T01:00:00Z"]
    doy = ds["day_of_year"].values.tolist()
    assert doy == [1, 1]
