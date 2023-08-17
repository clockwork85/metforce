import sys
from loguru import logger

# Set to DEBUG for more verbose logging
# Set to TRACE for even more verbose logging
logger.remove()
logger.add(sys.stderr, level="DEBUG")

def set_loglevel(verbosity: int) -> None:
    logger.remove()
    if verbosity == 1:
        logger.add(sys.stderr, level="DEBUG")
    elif verbosity >= 2:
        logger.add(sys.stderr, level="TRACE")
    else:
        logger.add(sys.stderr, level="INFO")

