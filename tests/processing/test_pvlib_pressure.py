# tests/processing/test_pvlib_pressure.py
"""
What this file tests:
1) The pvlib shortwave split receives the configured source's pressure, converted
   from mbar to Pa, for gridded (NLDAS-2) and station sources alike.
2) With no pressure parameter or no source frame, the split gets None and falls
   back to its elevation estimate, without raising.

Why this matters:
- Source frames store pressure under the internal "pressure" column. The split
  used to look for the station's raw key (BP_mbar), which never exists after the
  load renames it, so measured pressure never reached pvlib for any source.
"""

import pandas as pd
import pytest

import metforce.processing.derived_data as derived_data

IDX = pd.date_range("2025-06-29 17:00", periods=3, freq="1h", tz="UTC")


def _frames(pressure_source, pressure_mbar):
    shortwave = pd.DataFrame({"global_shortwave": [700.0, 750.0, 720.0]}, index=IDX)
    frames = {
        "nldas2": shortwave,
        "pvlib": pd.DataFrame({"zenith": [35.0, 32.0, 30.0]}, index=IDX),
    }
    if pressure_source is not None:
        frame = frames.get(pressure_source, pd.DataFrame(index=IDX))
        frames[pressure_source] = frame.assign(pressure=pressure_mbar)
    return frames


def _params(pressure_source):
    params = {
        "global_shortwave": {"source": "nldas2"},
        "zenith": {"source": "pvlib"},
        "direct_shortwave": {"source": "pvlib_disc"},
        "diffuse_shortwave": {"source": "pvlib_disc"},
    }
    if pressure_source is not None:
        params["pressure"] = {"source": pressure_source}
    return params


def _captured_pressure(mocker, params, frames):
    def fake_split(ghi, **kwargs):
        zero = ghi * 0.0
        return {"direct_shortwave": zero, "diffuse_shortwave": zero}

    split = mocker.patch.object(derived_data, "decompose_shortwave", side_effect=fake_split)
    derived_data.process_global_data(params, IDX, frames, latitude=31.0, longitude=-93.1, elevation=94.0)
    assert split.call_count == 1
    return split.call_args.kwargs["pressure_pa"]


@pytest.mark.parametrize("source", ["nldas2", "met"])
def test_split_gets_source_pressure_in_pa(mocker, source):
    pressure = _captured_pressure(mocker, _params(source), _frames(source, [1008.0, 1007.0, 1006.0]))
    assert list(pressure) == pytest.approx([100800.0, 100700.0, 100600.0])


def test_split_falls_back_without_pressure_parameter(mocker):
    assert _captured_pressure(mocker, _params(None), _frames(None, None)) is None


def test_split_falls_back_when_source_frame_is_missing(mocker):
    frames = _frames(None, None)
    frames["met"] = None  # the station strategy returns None when no station file is given
    assert _captured_pressure(mocker, _params("met"), frames) is None
