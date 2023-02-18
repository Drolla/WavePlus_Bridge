"""Performance Check

This file implements a performance check context manager that allows measuring
the execution time of code blocks.

Copyright (C) 2022 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import time
import logging

logger = logging.getLogger(__name__)


class PerformanceCheck(object):
    """Tasks performance checking

    Context manager to check the performance of tasks. It reports the
    execution time of the code placed in the with block.

    Args:
        task_short_name: Text that will be used in the performance logs
        log_level: Logging level, provided by the logging module.
                   Default=logging.INFO

    Example:
        from libs.performancecheck import PerformanceCheck

        with PerformanceCheck("Test loop"):
            value = 1.0
            for i in range(1000000):
                value = value*1.1
                if value > 1000:
                    value /= 1000
    """

    def __init__(self, task_short_name, log_level=logging.INFO):
        self.task_short_name = task_short_name
        self.log_level = log_level

    def __enter__(self):
        self.start_time = time.time()
        pass

    def __exit__(self, type, value, traceback):
        execution_time_ms = 1000*(time.time()-self.start_time)
        logger.log(self.log_level, "%s: %.3fms",
                   self.task_short_name, execution_time_ms)


#############################################
# Main
#############################################

if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    log_handler = logging.StreamHandler()
    log_handler.setLevel(logging.DEBUG)
    logger.addHandler(log_handler)

    # Do some stuff within the performance checker. This will report the
    # execution time of the with block.
    with PerformanceCheck("Test loop"):
        value = 1.0
        for i in range(1000000):
            value = value*1.1
            if value > 1000:
                value /= 1000
