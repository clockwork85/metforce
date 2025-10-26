import pandas as pd
import pytest

from metforce.processing.metstation import fill_in_missing_metdata

def _angle_close(a, b, atol=1e-2):
    d = (a - b + 180.0) % 360.0 - 180.0
    return abs(d) <= atol

def test_metstation_resample_vector_vs_legacy():
    # Minute-level raw samples over one 10-minute bin
    idx = pd.date_range("2020-01-01 00:00", periods=3, freq="1min", tz="UTC")
    met = pd.DataFrame({
        "WndSpd": [5.0, 5.0, 5.0],
        "WndDir": [350.0, 10.0, 20.0],
    }, index=idx)

    # mapping param -> column names (like your met_key in process_metstation_data)
    met_key = {
        "wind_speed": "WndSpd",
        "wind_direction": "WndDir",
    }

    # Final 10-min grid (one bin at :00)
    out_index = pd.date_range("2020-01-01 00:00", periods=1, freq="10min", tz="UTC")

    # Legacy scalar mean: direction is the naive arithmetic mean ⇒ ~126.667 deg
    legacy = fill_in_missing_metdata(
        met.copy(), met_key, out_index, metstation_freq="1min",
        interp_method="time",
        wind_avg_method="legacy_scalar",
        calm_threshold_mps=0.2,
    )
    assert pytest.approx(legacy.loc[out_index[0], "WndSpd"], rel=1e-12) == 5.0
    assert pytest.approx(legacy.loc[out_index[0], "WndDir"], rel=1e-6) == (350.0+10.0+20.0)/3.0

    # Vector-mean: direction collapses across 360°, ~6.7°, speed drops to ~4.883
    vec = fill_in_missing_metdata(
        met.copy(), met_key, out_index, metstation_freq="1min",
        interp_method="time",
        wind_avg_method="vector",
        calm_threshold_mps=0.2,
    )
    assert pytest.approx(vec.loc[out_index[0], "WndSpd"], rel=1e-3, abs=1e-3) == 4.883
    assert _angle_close(vec.loc[out_index[0], "WndDir"], 6.7)
