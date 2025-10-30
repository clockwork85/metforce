from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib
from pvlib import irradiance as pv_irr

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
) -> dict[str, pd.Series]:
    """
    Decompose GHI → DNI (beam-normal) + DHI (diffuse horizontal) using pvlib.
    Returns:
      - direct_shortwave: DNI (W m-2)  **beam-normal**
      - diffuse_shortwave: DHI (W m-2) **horizontal**

    Notes:
      - For 'disc' and 'dirint', pvlib returns DNI; we back out DHI via energy balance.
      - For 'erbs', pvlib returns both DNI and DHI.
      - For 'dirindex', we compute clear-sky GHI and feed it to pvlib.dirindex.
    """
    ghi = pd.Series(ghi, copy=False).clip(lower=0.0).astype(float)
    zenith = pd.Series(zenith, copy=False).astype(float)
    ghi, zenith = ghi.align(zenith, join="inner")
    times = ghi.index

    cosz = np.cos(np.radians(zenith.clip(upper=90.0)))
    cosz = cosz.where(cosz > 0, 0.0)

    m = method.lower()
    if m == "disc":
        dni = pv_irr.disc(ghi, zenith, times)["dni"]
    elif m == "dirint":
        # altitude is optional; include if we have it
        alt = float(elevation_m) if elevation_m is not None else None
        dni = pv_irr.dirint(ghi, zenith, times, altitude=alt)
    elif m == "dirindex":
        if elevation_m is None:
            raise ValueError("pvlib_dirindex requires elevation to compute clearsky.")
        ghi_cs, _dni_cs = _clearsky(times, latitude, longitude, float(elevation_m))
        # Support signature changes across pvlib versions:
        try:
            dni = pv_irr.dirindex(ghi, ghi_cs, zenith, times)
        except TypeError:
            try:
                dni = pv_irr.dirindex(ghi=ghi, ghi_clearsky=ghi_cs, zenith=zenith, times=times)  # newer kw
            except TypeError:
                dni = pv_irr.dirindex(ghi, zenith, times, clearsky=ghi_cs)  # fallback kw name
    elif m == "erbs":
        out = pv_irr.erbs(ghi, zenith, times)
        dni = out["dni"]
        dhi = out["dhi"].fillna(0.0)
    else:
        raise ValueError(f"Unknown pvlib decomposition method {method!r}")

    dni = pd.Series(dni, index=times).fillna(0.0).clip(lower=0.0)
    if m != "erbs":
        # Energy balance on the horizontal plane:  GHI = DNI*cos(z) + DHI
        dhi = (ghi - dni * cosz).clip(lower=0.0)

    return {
        "direct_shortwave": dni,    # **DNI**
        "diffuse_shortwave": dhi,   # **DHI**
    }