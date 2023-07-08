from typing import Union

import pandas as pd
import pytz

from logger_config import logger

# Read Met Data
def read_metstation_data(metfile: str) -> Union[pd.DataFrame, None]:
    if not metfile:
        return None
    else:
        try:
            logger.info(f"Reading metstation data from {metfile}")
            utc = pytz.UTC
            metdata = pd.read_excel(metfile, skiprows=[1], index_col=0)
            metdata.tz_localize(utc)
            logger.trace(f"{metdata[:50]=}")
        except ValueError:
            logger.error(f"Could not read metstation data from {metfile}")
            raise
    return metdata
