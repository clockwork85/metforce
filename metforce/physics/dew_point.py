import numpy as np
import pandas as pd

def dewpoint_from_t_rh(temp_c: pd.Series, rh_percent: pd.Series) -> pd.Series:
    """ Dew point (C) from air temp (C) and RH %"""
    t = pd.Series(temp_c, dtype=float)
    rh = pd.Series(rh_percent, dtype=float).clip(lower=0.0, upper=100.0) / 100.0
    a, b = 17.625, 243.04  # Magnus constants, -45 deg - 60 deg C
    gamma = np.log(rh) + (a * t) / ( b + t)
    td = (b * gamma) / (a - gamma)
    return td.reindex(t.index)

