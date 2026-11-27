# tests/processing/test_pressure_units.py
"""
What this file tests:
1) The NLDAS-2 NetCDF pressure getter returns mbar (hPa), the unit printed in the
   met file's Press column.
2) The NLDAS GRIB pressure getter returns mbar too.

Why this matters:
- Gridded surface pressure arrives in Pa. Readers of the met file (for example a
  thermal model that multiplies Press by 100 to get Pa) trust the "mbar" heading.
  Returning kPa (Pa / 1000) under that heading made those readers see a tenth of
  the real pressure.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest
import xarray as xr

from metforce.defaults import default_met_units
from metforce.processing.grib import GID, get_pressure_grib
from metforce.processing.nldas2 import get_pressure_nldas2


def test_met_file_press_column_is_mbar():
    assert default_met_units["pressure"] == "mbar"


def test_nldas2_pressure_is_mbar():
    ds = xr.Dataset(
        {"PSurf": (("lat", "lon"), np.array([[100800.0, 95000.0], [99000.0, 98000.0]]))},
        coords={"lat": [31.0, 31.125], "lon": [-93.125, -93.0]},
    )
    assert get_pressure_nldas2(ds, 31.0, -93.125) == pytest.approx(1008.0)


def test_grib_pressure_is_mbar(mocker):
    nearest = MagicMock()
    nearest.value = 100800.0  # Pa
    find = mocker.patch("eccodes.codes_grib_find_nearest", return_value=[nearest])
    gid_list = [None] * (GID.SURFACE_PRESSURE.value + 1)
    gid_list[GID.SURFACE_PRESSURE.value] = "surface-pressure-gid"

    assert get_pressure_grib(gid_list, 31.0, -93.125) == pytest.approx(1008.0)
    find.assert_called_once_with("surface-pressure-gid", 31.0, -93.125)
