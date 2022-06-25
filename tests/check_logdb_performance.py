"""LogDB performance check

This test program checks and reports the logging performance of the LogDB
module. It checks the performance with both the absolute logging method and the
delta logging method. With both methods, it adds two times 356*24*60 data sets
of 10 values each. The overall execution time is reported that allows checking
performance impact on changes applied on the LogDB module during development.

Copyright (C) 2022 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import os
import random
import sys
import shutil
import time
import unittest
import pickle

sys.path.append("../libs")
from logdb import LogDB as LogDB
from logdb import _LogDbCsv as LogDbCsv


def make_orderer():
    '''
    Ordered unit tests
    See: https://codereview.stackexchange.com/questions/122532/controlling-the-order-of-unittest-testcases
    '''

    order = {}

    def ordered(f):
        order[f.__name__] = len(order)
        return f

    def compare(*argv):
        if argv[-2] not in order:
            return 1
        if argv[-1] not in order:
            return -1
        return [1, -1][order[argv[-2]] < order[argv[-1]]]

    return ordered, compare

ordered, test_order_compare = make_orderer()

class LogDbTestClass(unittest.TestCase):
    DEBUG = False
    INIT_RELOAD_SIZE = 100
    TMP_DIR = "tmp_test_logdb/"
    VALUE_UPDATE_RATE = 0.2

    def open_db(self, labels, log_delta):
        try:
            os.remove(self.TMP_DIR + "test.csv")
        except FileNotFoundError:
            pass

        self.ldb = LogDB(labels, self.TMP_DIR + "test.csv", log_delta=log_delta)

        self.time = int(time.time())

    def close_db(self, store_to = None):
        del self.ldb
        if store_to is not None:
            try:
                os.remove(self.TMP_DIR + store_to + ".csv")
            except FileNotFoundError:
                pass
            os.rename(self.TMP_DIR + "test.csv",
                      self.TMP_DIR + store_to + ".csv")

    def append_data(self, nbr_data_sets):
        labels = self.ldb.labels[1:]
        data_set = {}
        for ds_count in range(nbr_data_sets):
            for label in labels:
                data = random.randrange(0, 1000)/10
                if random.random() < self.VALUE_UPDATE_RATE:
                    data_set[label] = data
            self.ldb.insert(data_set, tstamp=self.time)
            self.time += 1
    
    #### All tests ###

    def setUp(self):
        LogDB.DEBUG = self.DEBUG
        LogDbCsv.DEBUG = self.DEBUG
        LogDbCsv.INIT_RELOAD_SIZE = self.INIT_RELOAD_SIZE
        try:
            os.mkdir(self.TMP_DIR)
        except:
            pass


    #### Database creation and data adding ###

    @ordered
    def test_create_10_label_add_356x24x60_values_no_delta(self):
        self.open_db({
            "room0": ["sens0", "sens1", "sens2", "sens3", "sens4"],
            "room1": ["sens0", "sens1", "sens2", "sens3", "sens4"]
        }, log_delta=False)
        self.append_data(356 * 24 * 60)
        self.close_db(store_to="test_create_10_label_add_356x24x60_values_no_delta")

    def test_create_10_label_add_356x24x60_values_delta(self):
        self.open_db({
            "room0": ["sens0", "sens1", "sens2", "sens3", "sens4"],
            "room1": ["sens0", "sens1", "sens2", "sens3", "sens4"]
        }, log_delta=True)
        self.append_data(356 * 24 * 60)
        self.close_db(store_to="test_create_10_label_add_356x24x60_values_delta")


def help():
    print("Test debug and variations:")
    print("  python test_logdb.py [-h|-help] [-debug <Test>]")
    print("\nStandard Unit test options:")
    sys.argv = [sys.argv[0], "-h"]
    unittest.main()


#### Main test program ####

if __name__ == '__main__':

    argv = sys.argv
    random_seed = int(time.time())
    random.seed(a=random_seed)
    debug_test = None
    while len(argv) > 1:
        argv = argv[1:]
        if argv[0] in ("-h", "-help"):
            help()
        elif argv[0] == "-debug":
            argv = argv[1:]
            debug_test = argv[0]
            LogDbTestClass.DEBUG = True
        elif argv[0] == "-seed":
            argv = argv[1:]
            random.seed(a=int(argv[0]))

    if debug_test is not None:
        tc = LogDbTestClass()
        tc.setUp()
        getattr(tc, debug_test)()
    else:
        unittest.util._MAX_LENGTH=2000
        unittest.TestLoader.sortTestMethodsUsing = test_order_compare
        unittest.main(verbosity=2)
