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

def s2ivstr(seconds):
    """Seconds to intervall string"""
    seconds = int(seconds)
    return ":".join([
        str(seconds//3600).zfill(2),
        str((seconds//60) % 60).zfill(2),
        str(seconds % 60).zfill(2)
    ])

def define_tests():
    global times, values, test_vectors
    
    test_definitions = [line.split() for line in """
            above   10  10  10  10  10,20
            below    -   -   -   -      -
            for		 -  60   -  60     60
            min_iv   -   - 120 120    120
        time value
        0        9   0   0   0   0      0
        30      10   0   0   0   0      0
        60      15   1   0   1   0      0
        90      20   2   0   1   0      0
        120     25   3   1   1   1      1
        150     30   4   2   1   1      1
        180     35   5   3   2   1      2
        210     40   6   4   2   1      2
        240     45   7   5   2   2      2
        270     50   8   6   2   2      2
        300     50   9   7   3   2      3
       1000      0   9   7   3   2      3
       1060     25  10   7   4   2      3
       1090     25  11   7   4   2      3
       1120     15  12   8   4   3      4
       1150     15  13   9   4   3      4
       1180     15  14  10   5   3      4
    """.strip().split("\n")]

    nbr_tests = len(test_definitions[0])-1
    sequence_length = len(test_definitions)-5

    times = []
    values = []
    for row in test_definitions[5:5+sequence_length]:
        times.append(int(row[0]))
        values.append(int(row[1]))
    
    test_vectors = []
    for test in range(0, nbr_tests):
        config = {}
        if test_definitions[0][test+1] != "-":
            config["above"] = \
                [float(str) for str in test_definitions[0][test+1].split(",")]
        if test_definitions[1][test+1] != "-":
            config["below"] = \
                [float(str) for str in test_definitions[1][test+1].split(",")]
        if test_definitions[2][test+1] != "-":
            config["for"] = s2ivstr(test_definitions[2][test+1])
        if test_definitions[3][test+1] != "-":
            config["min_interval"] = s2ivstr(test_definitions[3][test+1])
        trigger_counts = [int(row[test+2]) for row in test_definitions[5:5+sequence_length]]
        test_vectors.append({
            "trigger_config": config,
            "trigger_counts": trigger_counts
        })

define_tests()

class TriggerTest(unittest.TestCase):

    def action(self, value):
        self.action_counter += 1

    def get_time(self):
        return self.emulated_time

    def inc_time(self, time_increment=60):
        self.emulated_time += time_increment

    def setUp(self):
        self.action_counter = 0
        self.emulated_time = int(time.time())
        self.time_method = time.time
        time.time = self.get_time

    def tearDown(self):
        time.time = self.time_method
    
    def generic_test(self, test_nbr):
        vector = test_vectors[test_nbr]
        trigger_action = Trigger(vector["trigger_config"], [self.action])
        #print(vector["trigger_config"])
        #print("", "S :", self.get_time())
        for index in range(len(times)):
            self.inc_time(0 if index==0 else times[index]-times[index-1])
            #print("", index, ":", self.get_time(), values[index], vector["trigger_counts"][index])
            trigger_action.log(values[index])
            self.assertEqual(self.action_counter, vector["trigger_counts"][index])

    def test_0(self):
        self.generic_test(0)

    def test_1(self):
        self.generic_test(1)

    def test_2(self):
        self.generic_test(2)

    def test_3(self):
        self.generic_test(3)

    def test_4(self):
        self.generic_test(4)


if __name__ == '__main__':
    unittest.main()
