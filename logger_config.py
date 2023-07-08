import sys
from loguru import logger

# Set to DEBUG for more verbose logging
# Set to TRACE for even more verbose logging
logger.remove()
logger.add(sys.stderr, level="TRACE")