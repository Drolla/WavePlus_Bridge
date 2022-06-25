"""Unit test for the LogDB module

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

class RefDb():
    DEBUG = False
    
    def __init__(self, label_specs, restore_file = None,
                 number_retention_records = None):
        all_labels = []
        current_labels = []
        restored_data = []

        if restore_file is not None:
            fpick = open(restore_file, 'rb')
            all_data = pickle.load(fpick)
            fpick.close()

            all_labels = all_data[0]
            restored_data = all_data[2]
        
        if isinstance(label_specs, dict):
            for main_label, sub_labels in label_specs.items():
                for sub_label in sub_labels:
                    label = main_label+':'+sub_label
                    if label not in all_labels:
                        all_labels.append(label)
                    current_labels.append(label)
        else:
            for label in label_specs:
                if label not in all_labels:
                    all_labels.append(label)
                current_labels.append(label)
        
        data = []
        for restored_ds in restored_data:
            ds = {}
            for index, value in restored_ds.items():
                if index in current_labels or index == "Time":
                    ds[index] = value
            data.append(ds)
        
        if number_retention_records is not None:
            data = data[-number_retention_records:]

        self.all_labels = all_labels
        self.current_labels = current_labels
        self.number_retention_records = number_retention_records
        self.data = data
            

    def close(self, store_file = None):
        if store_file is not None:
            all_data = [
                self.all_labels,
                self.current_labels,
                self.data,
            ]
            fpick = open(store_file, 'wb')
            pickle.dump(all_data, fpick)
            fpick.close()

    def insert(self, data_set, labels = None):
        if self.DEBUG:
            print("RefDb - insert:", data_set)
        self.data.append(data_set.copy())
        if self.number_retention_records is not None:
            self.data = self.data[-self.number_retention_records:]


    def get(self):
        if self.DEBUG:
            print("RefDb - get:")
            for ds in self.data:
                print("  ", ds)
        return self.data


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

class LogDbTest(unittest.TestCase):
    DEBUG = False
    TMP_DIR = "tmp_test_logdb/"
    
    def file_name(self, file_name):
        return self.TMP_DIR + self.__class__.__name__ + "__" + file_name

    def open_db(self, labels,
            init = False, restore_from = None, log_delta = False,
            number_retention_records = None):
        try:
            os.remove(self.file_name("test.csv"))
        except FileNotFoundError:
            pass

        if restore_from is not None:
            shutil.copyfile(self.file_name(restore_from + ".csv"),
                            self.file_name("test.csv"))
            self.rdb = RefDb(
                    labels,
                    restore_file = self.file_name(restore_from + ".bin"),
                    number_retention_records = number_retention_records)
        else:
            self.rdb = RefDb(labels)
        
        self.ldb = LogDB(
                labels, self.file_name("test.csv"),
                log_delta = log_delta,
                number_retention_records = number_retention_records)

        self.time = int(time.time())

    def close_db(self, store_to = None):
        del self.ldb

        if store_to is not None:
            try:
                os.remove(self.file_name(store_to + ".csv"))
            except FileNotFoundError:
                pass
            os.rename(self.file_name("test.csv"),
                      self.file_name(store_to + ".csv"))
            self.rdb.close(self.file_name(store_to + ".bin"))
        else:
            self.rdb.close()
      

    def append_data(self, nbr_data_sets, labels = None, update_rate = 1.0):
        if labels is None:
            labels = self.rdb.current_labels
        ref_data_set = {}
        for ds_count in range(nbr_data_sets):
            ref_data_set["Time"] = self.time
            for label in labels:
                data = random.randrange(0, 100)/10
                if random.random() < update_rate:
                    ref_data_set[label] = data
            self.rdb.insert(ref_data_set)

            if labels == self.rdb.current_labels == len(ref_data_set)-1:
                data_set = [ref_data_set[label] for label in labels]
                self.ldb.insert(data_set, tstamp=self.time)
            else:
                data_set = ref_data_set.copy()
                del data_set["Time"]
                self.ldb.insert(data_set, tstamp=self.time)

            self.time += 1
    
    #### All tests ###

    def setUp(self):
        LogDB.DEBUG = self.DEBUG
        LogDbCsv.DEBUG = self.DEBUG
        try:
            os.mkdir(self.TMP_DIR)
        except:
            pass

    def tearDown(self):
        try:
            del self.ldb
        except:
            pass

    #### Database creation and data adding ###

    # Log_delta = False

    @ordered
    def test_logdb__create3label_add0value(self):
        self.open_db(["sens0", "sens1", "sens2"], init=True, log_delta=False)
        self.assertEqual(self.ldb.labels[1:], self.rdb.current_labels)
        self.assertEqual(self.ldb.get(), self.rdb.get())
        self.close_db(store_to="test_logdb__create3label_add0value")

    @ordered
    def test_logdb__create3label_add5value(self):
        self.open_db(["sens0", "sens1", "sens2"], init=True, log_delta=False)
        self.append_data(5)
        self.close_db(store_to="test_logdb__create3label_add5value")

    @ordered
    def test_logdb__create3label_add100value(self):
        self.open_db(["sens0", "sens1", "sens2"], init=True, log_delta=False)
        self.append_data(100)
        self.close_db(store_to="test_logdb__create3label_add100value")

    @ordered
    def test_logdb__create3label_add10000value(self):
        self.open_db(["sens0", "sens1", "sens2"], init=True, log_delta=False)
        self.append_data(10000)
        self.close_db(store_to="test_logdb__create3label_add10000value")

    # Log_delta = True

    @ordered
    def test_logdb__create3label_add0value__delta(self):
        self.open_db(["sens0", "sens1", "sens2"], init=True, log_delta=True)
        self.assertEqual(self.ldb.labels[1:], self.rdb.current_labels)
        self.assertEqual(self.ldb.get(), self.rdb.get())
        self.close_db(store_to="test_logdb__create3label_add0value__delta")

    @ordered
    def test_logdb__create3label_add5value__delta(self):
        self.open_db(["sens0", "sens1", "sens2"], init=True, log_delta=True)
        self.append_data(5)
        self.close_db(store_to="test_logdb__create3label_add5value__delta")

    @ordered
    def test_logdb__create3label_add10000value__delta(self):
        self.open_db(["sens0", "sens1", "sens2"], init=True, log_delta=True)
        self.append_data(10000, update_rate=0.2)
        self.close_db(store_to="test_logdb__create3label_add10000value__delta")

    #### Database reopen, no label extension ###

    # Log_delta = False

    @ordered
    def test_logdb__reopen3label0value_1reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add0value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label0value_10reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 10
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add0value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label0value_10000reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 10000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add0value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label5value_1reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label5value_10reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 10
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label5value_1000reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label5value_100000reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 100000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label100value_1reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add100value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label100value_10reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 10
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add100value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label100value_1000reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add100value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label100value_100000reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 100000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add100value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label10000value_1reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add10000value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label10000value_10reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 10
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add10000value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label10000value_1000reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add10000value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label10000value_100000reloadsize(self):
        LogDbCsv.INIT_RELOAD_SIZE = 100000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add10000value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    # Log_delta = True

    @ordered
    def test_logdb__reopen3label5value_1reloadsize_delta(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value__delta",
                log_delta=True)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label5value_100000reloadsize_delta(self):
        LogDbCsv.INIT_RELOAD_SIZE = 100000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value__delta",
                log_delta=True)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label10000value_1reloadsize_delta(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add10000value__delta",
                log_delta=True)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label10000value_10reloadsize_delta(self):
        LogDbCsv.INIT_RELOAD_SIZE = 10
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add10000value__delta",
                log_delta=True)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label10000value_1000reloadsize_delta(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add10000value__delta",
                log_delta=True)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    #### Database reopen, label extension ###

    @ordered
    def test_logdb__reopen3label5value_1reloadsize_simpleextension_a(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2", "sens3", "sens4"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label5value_1reloadsize_simpleextension_b(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens1", "sens0", "sens2", "sens3", "sens4"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label5value_1reloadsize_simpleextension_c(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens1", "sens0", "sens4", "sens3", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label5value_1reloadsize_simpleextension_d(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens4", "sens3", "sens2", "sens1", "sens0"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    @ordered
    def test_logdb__reopen3label5value_1reloadsize_complex_extension_a(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db({
            "room0": ["sens0", "sens1", "sens2", "sens3", "sens4"],
            "room1": ["sens0", "sens1", "sens2", "sens3", "sens4"]
        }, restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    #### Database reopen, no label extension, new data added ###

    # Log_delta = False

    @ordered
    def test_logdb__reopen3label5value_1reloadsize_fullretention_add1value(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        #print("#### Restored DB ####")
        #self.ldb.get()
        #self.rdb.get()
        #print("#### Add new values ####")
        self.append_data(1)
        #print("#### Extended DB ####")
        self.assertEqual(self.ldb.get(), self.rdb.get())

    def test_logdb__reopen3label5value_1reloadsize_2retention_add1value(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False, number_retention_records=2)
        self.assertLessEqual(len(self.ldb.data["Time"]), 2)
        self.append_data(1)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    def test_logdb__reopen3label5value_1reloadsize_2retention_add3value(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False, number_retention_records=2)
        self.assertLessEqual(len(self.ldb.data["Time"]), 2)
        self.append_data(3)
        self.assertLessEqual(len(self.ldb.data["Time"]), 2)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    def test_logdb__reopen3label100value_1reloadsize_20retention_add1value(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add100value",
                log_delta=False, number_retention_records=20)
        self.assertLessEqual(len(self.ldb.data["Time"]), 20*1.1)
        self.append_data(1)
        self.assertLessEqual(len(self.ldb.data["Time"]), 20*1.1)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    def test_logdb__reopen3label100value_1reloadsize_20retention_add2value(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add100value",
                log_delta=False, number_retention_records=20)
        self.assertLessEqual(len(self.ldb.data["Time"]), 20*1.1)
        self.append_data(2)
        self.assertLessEqual(len(self.ldb.data["Time"]), 20*1.1)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    def test_logdb__reopen3label100value_1reloadsize_20retention_add3value(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add100value",
                log_delta=False, number_retention_records=20)
        self.assertLessEqual(len(self.ldb.data["Time"]), 20*1.1)
        self.append_data(3)
        self.assertLessEqual(len(self.ldb.data["Time"]), 20*1.1)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    def test_logdb__reopen3label100value_1reloadsize_20retention_add5value(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add100value",
                log_delta=False, number_retention_records=20)
        self.assertLessEqual(len(self.ldb.data["Time"]), 20*1.1)
        self.append_data(5)
        self.assertLessEqual(len(self.ldb.data["Time"]), 20*1.1)
        self.assertEqual(self.ldb.get(), self.rdb.get())

    #### CSV export ###

    @ordered
    def todo_logdb__reopen3label5value_csvexport_order_1(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(
                self.ldb.get_csv(["sens0", "sens1", "sens2"]),
                "No ref available")

    @ordered
    def todo_test_logdb__reopen3label5value_csvexport_order_2(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(
                self.ldb.get_csv(["sens2", "sens1", "sens0"]),
                "No ref available")

    @ordered
    def todo_test_logdb__reopen3label5value_csvexport_order_3(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1000
        self.open_db(["sens0", "sens1", "sens2"],
                restore_from="test_logdb__create3label_add5value",
                log_delta=False)
        self.assertEqual(
                self.ldb.get_csv(["sens1", "sens1"]),
                "No ref available")

    #### Database reopen, with missing data and whitespaces ###

    @ordered
    def test_logdb__reopen3label5value_missingdata(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        csv_file = self.TMP_DIR + "test_reopen_3_label_5_values_missingdata.csv"
        
        # Generate reference CSV file
        csv_file_content = \
            "logdbcsv,version=1.0,delta=0\n" + \
            "Time,sens0,sens1,sens2\n" + \
            "1590994497,9.8,9.0,6.5\n" + \
            "1590994498,,1.4,\n" + \
            "1590994498, ,1.4, \r\n" + \
            "1590994499,3.1,1.3,3.6\n" + \
            "1590994500,7.6,3.5,6.0\n" + \
            "1590994501,5.7,1.8,5.1\n"
        f = open(csv_file, "w")
        f.write(csv_file_content)
        f.close()

        # Load the CVS file
        ldb = LogDB(["sens0", "sens1", "sens2"], csv_file, log_delta=False)
        
        # Replace nan's by "nan" strings (to allow data validation with 
        # assertEqual)
        data = {}
        for label in ldb.data.keys():
            data[label] = ldb.data[label].tolist()
            for index, value in enumerate(data[label]):
                if value != value:
                    data[label][index] = "nan"
        
        # Check result
        self.assertEqual(data, {
            'Time': [1590994497.0,1590994498.0,1590994498.0,1590994499.0,1590994500.0,1590994501.0],
            'sens0': [9.8, "nan", "nan", 3.1, 7.6, 5.7],
            'sens1': [9.0,   1.4,  1.4, 1.3, 3.5, 1.8],
            'sens2': [6.5, "nan", "nan", 3.6, 6.0, 5.1]
        })

    @ordered
    def test_logdb__reopen3label5value_missingdata__delta(self):
        LogDbCsv.INIT_RELOAD_SIZE = 1
        csv_file = self.TMP_DIR + "test_reopen_3_label_5_values_missingdata__delta.csv"
        
        # Generate reference CSV file
        csv_file_content = \
            "logdbcsv,version=1.0,delta=1\n" + \
            "Time,sens0,sens1,sens2\n" + \
            "1590994497,9.8,9.0,6.5\n" + \
            "1590994498,,1.4,\n" + \
            "1590994498, ,1.4, \r\n" + \
            "1590994498,n,1.4, n \r\n" + \
            "1590994499,3.1,1.3,3.6\n" + \
            "1590994500,7.6,3.5,6.0\n" + \
            "1590994501,5.7,1.8,5.1\n"
        f = open(csv_file, "w")
        f.write(csv_file_content)
        f.close()

        # Load the CVS file
        ldb = LogDB(["sens0", "sens1", "sens2"], csv_file, log_delta=True)
        
        # Replace nan's by "nan" strings (to allow data validation with 
        # assertEqual)
        data = {}
        for label in ldb.data.keys():
            data[label] = ldb.data[label].tolist()
            for index, value in enumerate(data[label]):
                if value != value:
                    data[label][index] = "nan"
        
        # Check result
        self.assertEqual(data, {
            'Time': [1590994497.0,1590994498.0,1590994498.0,1590994498.0,1590994499.0,1590994500.0,1590994501.0],
            'sens0': [9.8,   9.8,  9.8, "nan", 3.1, 7.6, 5.7],
            'sens1': [9.0,   1.4,  1.4,   1.4, 1.3, 3.5, 1.8],
            'sens2': [6.5,   6.5,  6.5, "nan", 3.6, 6.0, 5.1]
        })


def help():
    print("Test debug and variations:")
    print("  python test_logdb.py -h|--help")
    print("  python test_logdb.py --list")
    print("  python test_logdb.py --debug [TestClass.]<Test>")
    print("  python test_logdb.py [Unit test options]")
    print("\nDebug example:")
    print("  test_logdb.py --debug test_logdb__reopen3label100value_1reloadsize_allreload_add3value")
    print("\nStandard Unit test:")
    sys.argv = [sys.argv[0], "-h"]
    unittest.main()

def list_tests():
    print("Available tests:")
    for glo in globals():
        if "Test" not in glo:
            continue
        print(" ", glo)
        for method in eval("dir(" + glo + ")"):
            if method[0:5] != "test_":
                continue
            print("   ", method)
    sys.exit(0)

if __name__ == '__main__':
    argv = sys.argv
    random_seed = int(time.time())
    print("random.seed:", random_seed)
    random.seed(a=random_seed)
    debug_test = None
    while len(argv) > 1:
        argv = argv[1:]
        if argv[0] in ("-h", "--help"):
            help()
        elif argv[0] in ("-l", "--list"):
            list_tests()
        elif argv[0] == "--debug":
            argv = argv[1:]
            debug_test = argv[0]
        elif argv[0] == "--reload_size":
            argv = argv[1:]
            LogDbTest.INIT_RELOAD_SIZE = argv[0]
        elif argv[0] == "--seed":
            argv = argv[1:]
            random.seed(a=int(argv[0]))
    
    if debug_test is not None:
        LogDbTest.DEBUG = True
        RefDb.DEBUG = True
        tc = LogDbTest()
        tc.setUp()
        #tc.test_5_open_add_extension_to_2x5()
        getattr(tc, debug_test.split(".")[-1])()
    else:
        unittest.util._MAX_LENGTH=2000
        unittest.TestLoader.sortTestMethodsUsing = test_order_compare
        unittest.main()
