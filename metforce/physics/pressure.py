from __future__ import annotations

def pressure_from_elevation_m(elevation_m: float) -> float:
    """ return STD pressure (Pa) for a site elevation """
    return 101325.0 * (1.0 - 2.25577e-5 * float(elevation_m)) ** 5.2559