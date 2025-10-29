# tests/processing/test_pvlib_dirindex.py
import numpy as np
import pandas as pd
import pvlib

from metforce.processing.derived_data import process_global_data

def _site():
    return dict(latitude=35.0844, longitude=-106.6504, elevation=1619.0)  # Albuquerque

def _times():
    # Daylight hours only to avoid cosz=0 edge cases
    return pd.date_range("2023-06-21 16:00", periods=5, freq="1h", tz="UTC")

def _zenith(times, site):
    loc = pvlib.location.Location(**site, tz="UTC")
    return loc.get_solarposition(times)["zenith"]

def _clearsky(times, site):
    loc = pvlib.location.Location(**site, tz="UTC")
    cs = loc.get_clearsky(times, model="ineichen", perez_enhancement=True)
    return cs["ghi"], cs["dni"]

def test_dirindex_matches_clearsky_dni():
    site = _site()
    times = _times()
    zen = _zenith(times, site)
    ghi_cs, dni_cs = _clearsky(times, site)

    # prepare inputs for process_global_data
    parameters = {
        "global_shortwave": {"source": "met"},
        "direct_shortwave": {"source": "pvlib_dirindex"},
        "diffuse_shortwave": {"source": "pvlib_dirindex"},
        "zenith": {"source": "pvlib"},
    }
    dfs = {
        "met":   pd.DataFrame({"global_shortwave": ghi_cs}, index=times),
        "pvlib": pd.DataFrame({"zenith": zen}, index=times),
    }

    out = process_global_data(parameters, times, dfs, **site)
    # Expect DNI ≈ DNI_clearsky (tolerance for model nuances)
    assert np.allclose(out["direct_shortwave"], dni_cs, rtol=0.08, atol=5.0)

    # And DHI ≈ GHI − DNI·cos(z)
    cosz = np.cos(np.radians(zen)).clip(lower=0)
    dhi_exp = ghi_cs - dni_cs * cosz
    assert np.allclose(out["diffuse_shortwave"], dhi_exp, rtol=0.08, atol=5.0)

def test_dirindex_with_dewpoint():
    site = _site()
    times = _times()
    zen = _zenith(times, site)
    ghi, dni_cs = _clearsky(times, site)  # use clear-sky inputs for determinism

    # synthetic T & RH with diurnal wiggle
    T = pd.Series(25.0 + np.sin(np.linspace(0, np.pi, len(times))), index=times)
    RH = pd.Series(50.0 + 5.0*np.cos(np.linspace(0, np.pi, len(times))), index=times)

    # Expected DNI from pvlib with temp_dew
    # (Use same dewpoint relation as library branch.)
    a, b = 17.625, 243.04
    r = (RH/100.0).clip(1e-6, 1.0)
    gamma = np.log(r) + (a*T)/(b + T)
    tdew = (b*gamma)/(a - gamma)

    p = 101325.0 * (1.0 - 2.25577e-5 * site["elevation"]) ** 5.25588
    dni_expected = pvlib.irradiance.dirindex(
        ghi, ghi, dni_cs, zen, times, pressure=p, temp_dew=tdew
    )

    parameters = {
        "global_shortwave": {"source": "met"},
        "direct_shortwave": {"source": "pvlib_dirindex"},
        "diffuse_shortwave": {"source": "pvlib_dirindex"},
        "zenith": {"source": "pvlib"},
        "temperature": {"source": "met"},
        "relative_humidity": {"source": "met"},
    }
    dfs = {
        "met":   pd.DataFrame({"global_shortwave": ghi, "temperature": T, "relative_humidity": RH}, index=times),
        "pvlib": pd.DataFrame({"zenith": zen}, index=times),
    }

    out = process_global_data(parameters, times, dfs, **site)
    assert np.allclose(out["direct_shortwave"], dni_expected, rtol=0.05, atol=5.0)
