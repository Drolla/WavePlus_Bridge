"""Trigger class

This file implements a trigger class used to generate alerts under configurable
conditions.

Copyright (C) 2020 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import time
import datetime


class Trigger:
    """Trigger base class.

    The constructor takes as argument the trigger condition as well as the
    action function(s) that will be called if the trigger condition is met.

    Args:
        config (dict): Trigger configuration
        action_functions (method or function): Action function(s)

    Trigger configuration:
        The trigger configuration is a dictionary that contains various keys
        that allow defining the exact conditions when a triggering should
        occur:

        above/below:
            A triggering happens if a sensor value is above or below a certain
            level. In this sense, the condition can be specified with the
            keywords 'above' or 'bellow' and a single threshold level (double)
            or as a list of threshold levels (list of doubles).
        for:
            This delays the trigger until the specified condition is valid for
            a time span specified either in seconds, or in the format
            Hours:Minutes:Seconds. The trigger delay is applied individually
            for each specified trigger threshold level:
        min_interval
            This allows specifying a minimum re-triggering interval. The
            provided value is specified either in seconds, or in the format
            Hours:Minutes:Seconds. The minimum re-triggering interval is not
            respected if the re-triggering is due to a higher trigger threshold
            level than the previously triggering.

    Action functions:
        The parameter action_functions accepts either a single function/method
        or a list of them. In case of a list of functions, all of them will be
        called if the trigger is activated. An action function will receive as
        first parameter the value provided to the log method, and as optional
        additional parameters eventual extra parameters provided to the log
        method.

    Example:
        # Define an action command
        def action(value):
            print("Trigger occurred at", value)

        # Setup the trigger
        trig = trigger.Trigger(
                config = {
                    'above': [100, 200, 500, 1000],
                    'for': '00:00:30',
                    'min_interval': '00:01:00'
                },
                action_functions = action
        )

        # Log values, the trigger will call the action command if the provided
        # value exceeds the specified thresholds
        trig.log(50)
        trig.log(100)
        trig.log(150)
    """

    def __init__(self, config, action_functions):
        def get_config(key, type, default=None):
            """Extracts a configuration key value and formats it if required"""

            value = config[key] if key in config else default
            if type == "list" and not isinstance(value, list):
                value = [value]
            elif value != default and type == "time_span":
                value = self._parse_time_span(value)
            return value

        # Get all configuration key values and perform parameter checks
        self.above = get_config("above", "list", [])
        self.below = get_config("below", "list", [])
        self.for_ = get_config("for", "time_span", 0)
        self.min_interval = get_config("min_interval", "time_span", 0)
        if self.above is None and self.below is None:
            raise Exception("AlertTrigger: 'above' or 'below' is required")

        # Transform the action function into a list if necessary
        self.actions = action_functions if isinstance(action_functions, list) \
                                        else [action_functions]

        # Initialize the instance variables
        self.first_trigger_time_above = [None]*len(self.above)
        self.first_trigger_time_below = [None]*len(self.below)
        self.trigger_index_above = -1
        self.trigger_index_below = -1
        self.last_alert_trigger = None

    @staticmethod
    def _parse_time_span(time_span_str):
        """Parse a time span string

        The method returns the parsed time span in seconds as float value.
        The time span string can have one of the following formats:
            * Hours:Minutes:Seconds
            * Seconds
        """

        try:
            t = datetime.datetime.strptime(time_span_str, "%H:%M:%S")
            return datetime.timedelta(
                    hours=t.hour, minutes=t.minute,
                    seconds=t.second).total_seconds()
        except Exception:
            pass
        try:
            return float(time_span_str)
        except Exception:
            raise Exception("Wrong time span format: {}".format(time_span_str))

    def _log_and_check_trigger(self, value):
        """Log a provided value and check if it activates the trigger"""

        # The current time is required to check 'for' and 'min_interval'
        # conditions
        current_time = time.time()

        # Check if the provided value is above or below the defined thresholds.
        # Register the index of the highest threshold level that is exceeded.
        # Ignore the level exceedance if required time span (parameter 'for')
        # is not met.
        trigger_index_above = -1
        for index, threashold in enumerate(self.above):
            if value <= threashold:
                self.first_trigger_time_above[index] = None
            elif self.first_trigger_time_above[index] is None:
                self.first_trigger_time_above[index] = current_time
            if self.first_trigger_time_above[index] is not None and \
                   current_time >= self.first_trigger_time_above[index] + \
                                   self.for_:
                trigger_index_above = index

        trigger_index_below = -1
        for index, threashold in enumerate(self.below):
            if value >= threashold:
                self.first_trigger_time_below[index] = None
            elif self.first_trigger_time_below[index] is None:
                self.first_trigger_time_below[index] = current_time
            if self.first_trigger_time_below[index] is not None and \
                   current_time >= self.first_trigger_time_below[index] + \
                                   self.for_:
                trigger_index_below = index

        # Evaluate if the trigger is active in function of the identified
        # threshold level exceedances. Suppress a retriggering within the
        # minimum interval time (parameter 'min_interval'), unless a higher
        # threshold level is exceeded.
        trigger_active = False
        if trigger_index_above >= 0 or trigger_index_below >= 0:
            if self.last_alert_trigger is not None and \
                    current_time >= self.last_alert_trigger+self.min_interval:
                trigger_active = True
            elif self.trigger_index_above != trigger_index_above or \
                    self.trigger_index_below != trigger_index_below:
                trigger_active = True

        # Store the current trigger information
        self.trigger_index_above = trigger_index_above
        self.trigger_index_below = trigger_index_below
        if trigger_active:
            self.last_alert_trigger = current_time
        return trigger_active

    def log(self, value, *args):
        """Log a provided value, and call the action functions if required
        """

        if self._log_and_check_trigger(value):
            for action in self.actions:
                action(value, *args)
