"""Unit test for the Trigger module

Copyright (C) 2022 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import sys
import time
import unittest

sys.path.append("../libs")
from trigger import Trigger as Trigger

class ParseTimeSpanTest(unittest.TestCase):
    def test_parse_time_span_0(self):
        self.assertEqual(
            Trigger.parse_time_span('00:30:00'),
            30*60)

class TriggerActionTest(unittest.TestCase):

    def action(self, value):
        self.action_counter += 1

    def get_time(self):
        return self.emulated_time

    def inc_time(self, time_increment=60):
        self.emulated_time += time_increment

    def setUp(self):
        self.action_counter = 0
        self.emulated_time = time.time()
        self.time_method = time.time
        time.time = self.get_time

    def tearDown(self):
        time.time = self.time_method
    
    def test_init_0(self):
        trigger_action = Trigger(
                {'above': 100, 'for': '00:30:00', 'min_interval': '01:00:00'},
                [self.action])
        self.assertEqual(self.action_counter, 0)

    def test_trigger_above_1(self):
        trigger_action = Trigger(
                {'above': 100},
                [self.action])
        self.assertEqual(self.action_counter, 0)
        
        trigger_action.log(-101)
        trigger_action.log(0)
        trigger_action.log(99)
        self.assertEqual(self.action_counter, 0)

        self.inc_time()
        trigger_action.log(100)
        self.assertEqual(self.action_counter, 0)

        self.inc_time()
        trigger_action.log(101)
        self.assertEqual(self.action_counter, 1)

        self.inc_time()
        trigger_action.log(200)
        self.assertEqual(self.action_counter, 2)

    def test_trigger_below_1(self):
        trigger_action = Trigger(
                {'below': 100},
                [self.action])
        self.assertEqual(self.action_counter, 0)
        
        trigger_action.log(300)
        trigger_action.log(200)
        self.assertEqual(self.action_counter, 0)

        self.inc_time()
        trigger_action.log(100)
        self.assertEqual(self.action_counter, 0)

        self.inc_time()
        trigger_action.log(99)
        self.assertEqual(self.action_counter, 1)

        self.inc_time()
        trigger_action.log(0)
        self.assertEqual(self.action_counter, 2)

    def test_trigger_for_1(self):
        trigger_action = Trigger(
                {'above': 100, 'for': '00:01:00'},
                [self.action])
        self.assertEqual(self.action_counter, 0)
        
        trigger_action.log(101)
        self.assertEqual(self.action_counter, 0)

        self.inc_time(30)
        trigger_action.log(101)
        self.assertEqual(self.action_counter, 0)

        self.inc_time(29)
        trigger_action.log(101)
        self.assertEqual(self.action_counter, 0)

        self.inc_time(1)
        trigger_action.log(101)
        self.assertEqual(self.action_counter, 1)

        for t in range(5):
            self.inc_time(1)
            trigger_action.log(101)
            self.assertEqual(self.action_counter, 2+t)

    def test_trigger_min_interval_1(self):
        trigger_action = Trigger(
                {'above': 100, 'min_interval': '00:01:00'},
                [self.action])
        self.assertEqual(self.action_counter, 0)
        
        trigger_action.log(101)
        self.assertEqual(self.action_counter, 1)

        for t in range(100):
            self.inc_time(20)
            trigger_action.log(101)
            self.assertEqual(self.action_counter, 1 + int((1+t)/3))

    def test_trigger_for_min_interval_1(self):
        trigger_action = Trigger(
                {'above': 100, 'for': '00:01:00', 'min_interval': '00:01:00'},
                [self.action])
        self.assertEqual(self.action_counter, 0)
        
        trigger_action.log(101)
        self.assertEqual(self.action_counter, 0)

        for t in range(100):
            self.inc_time(20)
            trigger_action.log(101)
            self.assertEqual(self.action_counter, 0 + int((1+t)/3))

    def test_trigger_multi_above_1(self):
        trigger_action = Trigger(
                {'above': [100, 200, 400, 1000, 2000], 'min_interval': '00:01:00'},
                [self.action])
        self.assertEqual(self.action_counter, 0)
        
        trigger_action.log(99)
        trigger_action.log(100)
        self.assertEqual(self.action_counter, 0)

        self.inc_time()
        trigger_action.log(101)
        self.assertEqual(self.action_counter, 1)

        trigger_action.log(150)
        self.assertEqual(self.action_counter, 1)

        trigger_action.log(200)
        self.assertEqual(self.action_counter, 1)

        trigger_action.log(201)
        self.assertEqual(self.action_counter, 2)

        self.inc_time()
        trigger_action.log(200)
        self.assertEqual(self.action_counter, 3)


if __name__ == '__main__':
    unittest.main()
