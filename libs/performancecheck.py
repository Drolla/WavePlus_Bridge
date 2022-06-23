"""Performance Check

This file implements a performance check class that allows measuring the
execution time of code blocks.

Copyright (C) 2022 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import time
import logging

logger = logging.getLogger(__name__)


class PerformanceCheck():
    """Tasks performance checking

    This class provides the tool to check the performance of tasks. It sets a
    time anchor when the object is created and it calculates and reports the
    passed time when the object is deleted again.
    """

    def __init__(self, task_description, log_level=logging.INFO):
        self.start_time = time.time()
        self.task_description = task_description
        self.log_level = log_level

    def __del__(self):
        execution_time_ms = 1000*(time.time()-self.start_time)
        logger.log(self.log_level, "Performance check, %s: %.3fms",
                   self.task_description, execution_time_ms)


#############################################
# Main
#############################################

if __name__ == "__main__":
    logger.setLevel(logging.WARNING)
    
    # Create a performance check instance
    pc = PerformanceCheck("Test loop")
    
    # Do some stuff and check the execution time (=performance check)
    value = 1.0
    for i in range(1000000):
        value = value*1.1
        if value > 1000:
            value /= 1000
    
    # Delete the performance checker. This will report the run time
    del pc
