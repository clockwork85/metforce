from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib
from pvlib import irradiance as pv_irr

from metforce.physics.pressure import  DEFAULT_PRESSURE_PA, _resolve_pressure_pa, _resolve_temp_dew_c

def _clearsky(times: pd.DatetimeIndex, latitude: float, longitude: float, elevation_m: float) -> tuple[pd.Series, pd.Series]:
    """Return (GHI_clear, DNI_clear) indexed to *times* (UTC)."""
    loc = pvlib.location.Location(latitude, longitude, altitude=float(elevation_m), tz="UTC")
    cs = loc.get_clearsky(times, model="ineichen", perez_enhancement=True)
    return cs["ghi"].astype(float), cs["dni"].astype(float)

def decompose_shortwave(
    ghi: pd.Series,
    zenith: pd.Series,
    method: str,
    *,
    latitude: float,
    longitude: float,
    elevation_m: float | int | None = None,
    # new/extended knobs:
    pressure_pa: float | pd.Series | None = None,
    temp_dew_c: float | pd.Series | None = None,
    temp_c: pd.Series | None = None,
    rh_percent: pd.Series | None = None,
    use_delta_kt_prime: bool = True,
    min_cos_zenith: float = 0.065,
    max_zenith: float = 87.0,
) -> dict[str, pd.Series]:
    """
    Decompose GHI → DNI (beam-normal) + DHI (diffuse horizontal) using pvlib.

    Returns
    -------
    dict
        {
          "direct_shortwave": DNI [W m-2],   # beam-normal
          "diffuse_shortwave": DHI [W m-2],  # diffuse horizontal
        }

    Parameters (selected)
    ---------------------
    pressure_pa : float | Series | None
        Surface pressure in Pascal. If None, will attempt to read from
        `ghi.attrs["pressure_pa"]` or `["pressure_mbar"]`, else estimate from
        `elevation_m`, else fall back to 101325 Pa.
    temp_dew_c : float | Series | None
        Dew-point temperature (°C). If None, and both `temp_c` and `rh_percent`
        are provided, dew-point is computed via Magnus (dewpoint_from_t_rh).
    use_delta_kt_prime, min_cos_zenith, max_zenith : pvlib model controls.

    Notes
    -----
    Energy balance on horizontal:  GHI = DNI * cos(zenith) + DHI.
    Methods:
      - 'disc'     → pvlib.irradiance.disc (we pass pressure, cosz/zenith limits).
      - 'dirint'   → pvlib.irradiance.dirint (we pass pressure + dew-point).
      - 'dirindex' → pvlib.irradiance.dirindex with clear-sky (Ineichen) GHI/DNI,
                     plus pressure + dew-point.
      - 'erbs'     → pvlib.irradiance.erbs (returns DNI and DHI directly).
    """
    # --- clean inputs & alignment ------------------------------------------------
    ghi = pd.Series(ghi, copy=False).clip(lower=0.0).astype(float)
    zenith = pd.Series(zenith, copy=False).astype(float)
    ghi, zenith = ghi.align(zenith, join="inner")
    times = ghi.index

    # daytime mask and cos(z)
    cosz = np.cos(np.radians(zenith.clip(upper=90.0)))
    cosz = cosz.where(cosz > 0.0, 0.0)

    # resolve pressure [Pa] (scalar or Series aligned to times)
    p_pa = _resolve_pressure_pa(pressure_pa, like=ghi, elevation_m=elevation_m)
    if isinstance(p_pa, pd.Series):
        p_pa = p_pa.reindex(times)

    # resolve dew-point [°C] if available
    td_c = _resolve_temp_dew_c(
        temp_dew_c=temp_dew_c,
        temp_c=temp_c,
        rh_percent=rh_percent,
        index=times,
    )

    # --- branch on method --------------------------------------------------------
    m = method.lower()
    if m == "disc":
        # pvlib.disc returns a DataFrame with 'dni','kt','airmass'
        out = pv_irr.disc(
            ghi=ghi,
            solar_zenith=zenith,
            times=times,
            pressure=p_pa if p_pa is not None else DEFAULT_PRESSURE_PA,
            min_cos_zenith=min_cos_zenith,
            max_zenith=max_zenith,
        )
        dni = out["dni"]

    elif m == "dirint":
        dni = pv_irr.dirint(
            ghi=ghi,
            solar_zenith=zenith,
            times=times,
            pressure=p_pa if p_pa is not None else DEFAULT_PRESSURE_PA,
            use_delta_kt_prime=use_delta_kt_prime,
            temp_dew=None if td_c is None else td_c,
            min_cos_zenith=min_cos_zenith,
            max_zenith=max_zenith,
        )

    elif m == "dirindex":
        if elevation_m is None:
            raise ValueError("pvlib_dirindex requires elevation to compute clear-sky.")
        ghi_clear, dni_clear = _clearsky(times, latitude, longitude, float(elevation_m))

        # Try modern kw names first (pvlib>=0.11.2); fallback to *_clearsky on older versions
        try:
            dni = pv_irr.dirindex(
                ghi=ghi,
                ghi_clear=ghi_clear,
                dni_clear=dni_clear,
                zenith=zenith,
                times=times,
                pressure=p_pa if p_pa is not None else DEFAULT_PRESSURE_PA,
                use_delta_kt_prime=use_delta_kt_prime,
                temp_dew=None if td_c is None else td_c,
                min_cos_zenith=min_cos_zenith,
                max_zenith=max_zenith,
            )
        except TypeError:
            dni = pv_irr.dirindex(
                ghi=ghi,
                ghi_clearsky=ghi_clear,
                dni_clearsky=dni_clear,
                zenith=zenith,
                times=times,
                pressure=p_pa if p_pa is not None else DEFAULT_PRESSURE_PA,
                use_delta_kt_prime=use_delta_kt_prime,
                temp_dew=None if td_c is None else td_c,
                min_cos_zenith=min_cos_zenith,
                max_zenith=max_zenith,
            )

    elif m == "erbs":
        out = pv_irr.erbs(ghi=ghi, zenith=zenith, times=times)
        dni = out["dni"].astype(float)
        dhi = out["dhi"].astype(float).fillna(0.0)

    else:
        raise ValueError(f"Unknown pvlib decomposition method {method!r}")

    # --- finish: compute DHI if needed; clip non-negatives; return ---------------
    dni = pd.Series(dni, index=times, name="direct_shortwave").fillna(0.0).clip(lower=0.0)

    if m != "erbs":
        # Energy balance on the horizontal plane
        dhi = (ghi - dni * cosz).rename("diffuse_shortwave").clip(lower=0.0)

    return {
        "direct_shortwave": dni,   # DNI (beam-normal)
        "diffuse_shortwave": dhi,  # DHI (horizontal)
    }
