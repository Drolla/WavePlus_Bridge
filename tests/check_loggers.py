"""Logger checks

Check the availability of the loggers of the main Wave Plus Bridge module and
the used modules.

Copyright (C) 2022 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import logging
import sys
sys.path.append("..")
import waveplus_bridge

# Get root logger for this local use
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Report all available loggers
print("\nLoggers:")

logging.info("  <root> : %s", logging.getLogger())
for name in list(logging.root.manager.loggerDict):
    logging.info("  %s : %s", name, logging.getLogger(name))


# Make a few tests with different loggers and different levels
print("\nLog tests:")

waveplus_bridge.logger.warning("  waveplus_bridge")
waveplus_bridge.logger.info("  waveplus_bridge")
waveplus_bridge.logger.debug("  waveplus_bridge")

waveplus_bridge.logdb.logger.warning("  logdb")
waveplus_bridge.logdb.logger.info("  logdb")
waveplus_bridge.logdb.logger.debug("  logdb")

print()
