"""Unit test for the CSV load/store operations of the LogDB module

Copyright (C) 2022 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import os
import sys
import shutil
import time
import array
import unittest
import pickle

sys.path.append("../libs")
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
    CSV_DELTA = False
    TMP_DIR = "tmp_test_logdb/"
    
    REF_DATA = [
        "5.8, nan, 6.8,    ,    ",
        "   ,    , 7.8, nan,    ",
        "6.8, 0.8, 7.8,    ,    ",
        "8.3, 0.8, 6.8, 1.3, 1.8",
        "8.3, 5.8, nan, 1.3,    ",
        "8.3, 5.8, nan, 1.3,    ",
        "0.3, 5.8, 5.8, 9.8, 9.3",
        "   ,    , 4.3,    , nan",
        "   , 8.3, 4.3,    , 7.8",
        "nan, 5.8,    , 4.3, 7.8",
        "0.3, 5.8, nan, 4.3, 7.8",
        "nan, nan,    , 4.3, 5.8",
        "nan, 6.8,    ,    ,    ",
        "   , 7.8, nan,    , 6.8",
        "0.8, 7.8,    ,    , 8.3",
    ]

    def open_db(self, labels, init=False, restore_from=None, log_delta=False):
        try:
            os.remove(self.TMP_DIR + "test.csv")
        except FileNotFoundError:
            pass

        if restore_from is not None:
            shutil.copyfile(self.TMP_DIR + restore_from + ".csv",
                            self.TMP_DIR + "test.csv")
        
        self.ldbcsv = LogDbCsv(
                            labels, self.TMP_DIR+"test.csv",log_delta=log_delta)

    def close_db(self, store_to=None):
        del self.ldbcsv

        if store_to is not None:
            try:
                os.remove(self.TMP_DIR + store_to + ".csv")
            except FileNotFoundError:
                pass
            os.rename(self.TMP_DIR + "test.csv",
                      self.TMP_DIR + store_to + ".csv")

    def append_data(self, labels, nbr_data_sets):
        data_set = {}
        for ds_count in range(nbr_data_sets):
            ref_data_set = self.REF_DATA[ds_count].split(",")
            old_data_set = data_set.copy()
            data_set = {}
            for label in labels:
                ref_value = ref_data_set.pop(0).strip()
                if ref_value == "":
                    pass
                else:
                    data_set[label] = float(ref_value)
            self.ldbcsv.insert(data_set)
    
    def get_csv_content(self, file):
        with open(self.TMP_DIR + file + ".csv", 'r') as f:
            file_content = f.readline().rstrip()
            file_content += "\n"
            file_content += f.readline().rstrip()
            file_content += "\n"
            file_content += f.read()
            return file_content.split("\n")

    @staticmethod
    def data_to_csv(labels, data):
        all_labels = []
        for label in labels + [*data.keys()]:
            if label not in all_labels:
                all_labels.append(label)

        all_lines = [', '.join(all_labels)]
        for index in range(len(data[all_labels[0]])):
            line_values = []
            for label in all_labels:
                value = data[label][index]
                line_values.append(str(value) if value==value else "nan")
            all_lines.append(', '.join(line_values))
        #print('all_lines:', "\n".join(all_lines))
        return all_lines
            
    @staticmethod
    def multi_line_trim(text):
        all_lines = []
        for line in text.split("\n"):
            all_lines.append(line.strip())
        if all_lines[0] == "":
            all_lines = all_lines[1:]
        return all_lines
        

    #### All tests ###

    def setUp(self):
        LogDbCsv.DEBUG = self.DEBUG
        LogDbCsv.CSV_DELTA = self.CSV_DELTA
        try:
            os.mkdir(self.TMP_DIR)
        except:
            pass


    #### CSV file loading ###
    
    # Check that the CSV file can be correctly loaded, also if the values are
    # surrounded with white spaces

    @ordered
    def test_logcsv__reload(self):
        labels = ["sens0", "sens1", "sens2"]
        csv_file = self.TMP_DIR + "test_logcsv__reload.csv"
        
        # Generate reference CSV file
        csv_file_content = [
            "logdbcsv,version=1.0,delta=0",
            "sens0,sens1,sens2",
            "1.3,3.3,0.3",
            "2.5,,2.3",
            "2.5, ,2.3",
            "3.6,5.3,",
            "3.6,5.3, \r",
            "4.7, n , 8.8",
            " 5.8 , 7.8 , 4.8 \r\n"
        ]
        f = open(csv_file, "w")
        f.write("\n".join(csv_file_content))
        f.close()
        
        # Load the CVS file
        data = {}
        for label in labels:
            data[label] = array.array('d')
        ldbcsv = LogDbCsv(labels, csv_file, log_delta=False)
        ldbcsv.restore_data(data)
        del ldbcsv
        
        # Check result
        self.assertEqual(
            self.data_to_csv(labels, data), [
            "sens0, sens1, sens2", 
            "1.3, 3.3, 0.3", 
            "2.5, nan, 2.3", 
            "2.5, nan, 2.3", 
            "3.6, 5.3, nan", 
            "3.6, 5.3, nan", 
            "4.7, nan, 8.8", 
            "5.8, 7.8, 4.8"
        ])

    @ordered
    def test_logcsv__reload__delta(self):
        labels = ["sens0", "sens1", "sens2"]
        csv_file = self.TMP_DIR + "test_logcsv__reload__delta.csv"
        
        # Generate reference CSV file
        csv_file_content = [
            "logdbcsv,version=1.0,delta=1",
            " sens0 , sens1,sens2 ",
            "1.3,3.3,0.3",
            "2.5,,2.3",
            ", ,",
            ", n ,",
            "3.6,5.3,",
            ",, \r",
            "4.7,2.8 , 8.8",
            " 5.8 , 7.8 , 4.8 \r\n"
        ]
        f = open(csv_file, "w")
        f.write("\n".join(csv_file_content))
        f.close()
        
        # Load the CVS file
        data = {}
        for label in labels:
            data[label] = array.array('d')
        ldbcsv = LogDbCsv(labels, csv_file, log_delta=True)
        ldbcsv.restore_data(data)
        del ldbcsv
        
        # Check result
        self.assertEqual(
            self.data_to_csv(labels, data), [
            "sens0, sens1, sens2", 
            "1.3, 3.3, 0.3", 
            "2.5, 3.3, 2.3", 
            "2.5, 3.3, 2.3", 
            "2.5, nan, 2.3", 
            "3.6, 5.3, 2.3", 
            "3.6, 5.3, 2.3", 
            "4.7, 2.8, 8.8", 
            "5.8, 7.8, 4.8"
        ])


    #### CSV file creation ###
    
    # Check that the CSV file is created correctly together with the header

    @ordered
    def test_logcsv__create5label_add0value(self):
        labels = ["sens0", "sens1", "sens2", "sens3", "sens4"]
        csv_file = "test_logcsv__create5label_add0value"

        self.open_db(labels, init=True)
        self.assertEqual(self.ldbcsv.labels, labels)
        self.close_db(store_to=csv_file)

        self.assertEqual(self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=0",
            "sens0,sens1,sens2,sens3,sens4",
            ""
        ])

    @ordered
    def test_logcsv__create5label_add0value__delta(self):
        labels = ["sens0", "sens1", "sens2", "sens3", "sens4"]
        csv_file = "test_logcsv__create5label_add0value__delta"

        self.open_db(labels, init=True, log_delta=True)
        self.assertEqual(self.ldbcsv.labels, labels)
        self.close_db(store_to=csv_file)

        self.assertEqual(self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=1",
            "sens0,sens1,sens2,sens3,sens4",
            ""
        ])


    #### Data logging ###
    
    # Check that the data value sets are correctly written into the CSV file

    @ordered
    def test_logcsv__create3label_add7value(self):
        labels = ["sens0", "sens1", "sens2"]
        csv_file = "test_logcsv__create3label_add7value"

        self.open_db(labels, init=True)
        self.append_data(labels, 7)
        self.close_db(store_to=csv_file)

        self.assertEqual(
            self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=0",
            "sens0,sens1,sens2",
            "5.8,,6.8",
            ",,7.8",
            "6.8,0.8,7.8",
            "8.3,0.8,6.8",
            "8.3,5.8,",
            "8.3,5.8,",
            "0.3,5.8,5.8",
            ""
        ])

    @ordered
    def test_logcsv__create3label_add7value__delta(self):
        labels = ["sens0", "sens1", "sens2"]
        csv_file = "test_logcsv__create3label_add7value__delta"

        self.open_db(labels, init=True, log_delta=True)
        self.append_data(labels, 7)
        self.close_db(store_to=csv_file)

        self.assertEqual(
            self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=1",
            "sens0,sens1,sens2",
            "5.8,n,6.8",
            "n,,7.8",
            "6.8,0.8,",
            "8.3,,6.8",
            ",5.8,n",
            ",,",
            "0.3,,5.8",
            ""
        ])

    @ordered
    def test_logcsv__create5label_add7value(self):
        labels = ["sens0", "sens1", "sens2", "sens3", "sens4"]
        csv_file = "test_logcsv__create5label_add7value"

        self.open_db(labels, init=True)
        self.append_data(labels, 7)
        self.close_db(store_to=csv_file)

        self.assertEqual(
            self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=0",
            "sens0,sens1,sens2,sens3,sens4",
            "5.8,,6.8,,",
            ",,7.8,,",
            "6.8,0.8,7.8,,",
            "8.3,0.8,6.8,1.3,1.8",
            "8.3,5.8,,1.3,",
            "8.3,5.8,,1.3,",
            "0.3,5.8,5.8,9.8,9.3",
            ""
        ])

    @ordered
    def test_logcsv__create5label_add7value__delta(self):
        labels = ["sens0", "sens1", "sens2", "sens3", "sens4"]
        csv_file = "test_logcsv__create5label_add7value__delta"

        self.open_db(labels, init=True, log_delta=True)
        self.append_data(labels, 7)
        self.close_db(store_to=csv_file)

        self.assertEqual(
            self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=1",
            "sens0,sens1,sens2,sens3,sens4",
            "5.8,n,6.8,n,n",
            "n,,7.8,,",
            "6.8,0.8,,,",
            "8.3,,6.8,1.3,1.8",
            ",5.8,n,,n",
            ",,,,",
            "0.3,,5.8,9.8,9.3",
            ""
        ])


    #### Label extension or reduction ###
    
    # Check that the data are correctly restored and the labels well extended.

    # 5 labels -> 5 labels:

    @ordered
    def test_logcsv__reopen5label7value_add5label5value(self):
        labels = ["sens0", "sens1", "sens2", "sens3", "sens4"]
        csv_file = "test_logcsv__reopen5label7value_add5label5value"

        self.open_db(labels, restore_from="test_logcsv__create5label_add7value")
        self.append_data(labels, 5)
        self.close_db(store_to=csv_file)

        self.assertEqual(
            self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=0",
            "sens0,sens1,sens2,sens3,sens4",
            "5.8,,6.8,,",
            ",,7.8,,",
            "6.8,0.8,7.8,,",
            "8.3,0.8,6.8,1.3,1.8",
            "8.3,5.8,,1.3,",
            "8.3,5.8,,1.3,",
            "0.3,5.8,5.8,9.8,9.3",

            "5.8,,6.8,,",
            ",,7.8,,",
            "6.8,0.8,7.8,,",
            "8.3,0.8,6.8,1.3,1.8",
            "8.3,5.8,,1.3,",
            ""
        ])

    @ordered
    def test_logcsv__reopen5label7value_add5label5value__delta(self):
        labels = ["sens0", "sens1", "sens2", "sens3", "sens4"]
        csv_file = "test_logcsv__reopen5label7value_add5label5value__delta"

        self.open_db(
                labels,
                restore_from="test_logcsv__create5label_add7value__delta",
                log_delta=True)
        self.append_data(labels, 5)
        self.close_db(store_to=csv_file)

        self.assertEqual(
            self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=1",
            "sens0,sens1,sens2,sens3,sens4",
            "5.8,n,6.8,n,n",
            "n,,7.8,,",
            "6.8,0.8,,,",
            "8.3,,6.8,1.3,1.8",
            ",5.8,n,,n",
            ",,,,",
            "0.3,,5.8,9.8,9.3",

            "5.8,n,6.8,n,n",
            "n,,7.8,,",
            "6.8,0.8,,,",
            "8.3,,6.8,1.3,1.8",
            ",5.8,n,,n",
            ""
        ])

    # 5 labels -> 3 labels:

    @ordered
    def test_logcsv__reopen5label7value_add2label5value(self):
        labels = ["sens1", "sens3"]
        csv_file = "test_logcsv__reopen5label7value_add2label5value"

        self.open_db(labels, restore_from="test_logcsv__create5label_add7value")
        self.append_data(labels, 5)
        self.close_db(store_to=csv_file)

        self.assertEqual(
            self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=0",
            "sens0,sens1,sens2,sens3,sens4",
            "5.8,,6.8,,",
            ",,7.8,,",
            "6.8,0.8,7.8,,",
            "8.3,0.8,6.8,1.3,1.8",
            "8.3,5.8,,1.3,",
            "8.3,5.8,,1.3,",
            "0.3,5.8,5.8,9.8,9.3",

            ",5.8,,,",
            ",,,,",
            ",6.8,,0.8,",
            ",8.3,,0.8,",
            ",8.3,,5.8,",
            ""
        ])

    #@ordered
    def test_logcsv__reopen5label7value_add2label5value__delta(self):
        labels = ["sens1", "sens3"]
        csv_file = "test_logcsv__reopen5label7value_add2label5value__delta"

        self.open_db(
                labels,
                restore_from="test_logcsv__create5label_add7value__delta",
                log_delta=True)
        self.append_data(labels, 5)
        self.close_db(store_to=csv_file)

        self.assertEqual(
            self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=1",
            "sens0,sens1,sens2,sens3,sens4",
            "5.8,n,6.8,n,n",
            "n,,7.8,,",
            "6.8,0.8,,,",
            "8.3,,6.8,1.3,1.8",
            ",5.8,n,,n",
            ",,,,",
            "0.3,,5.8,9.8,9.3",

            "n,5.8,n,n,n",
            ",n,,,",
            ",6.8,,0.8,",
            ",8.3,,,",
            ",,,5.8,",
            ""
        ])

    # 3 labels -> 5 labels:

    @ordered
    def test_logcsv__reopen3label7value_add5label5value(self):
        labels = ["sens0", "sens1", "sens2", "sens3", "sens4"]
        csv_file = "test_logcsv__reopen3label7value_add5label5value"

        self.open_db(labels, restore_from="test_logcsv__create3label_add7value")
        self.append_data(labels, 5)
        self.close_db(store_to=csv_file)

        self.assertEqual(
            self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=0",
            "sens0,sens1,sens2,sens3,sens4",
            "5.8,,6.8",
            ",,7.8",
            "6.8,0.8,7.8",
            "8.3,0.8,6.8",
            "8.3,5.8,",
            "8.3,5.8,",
            "0.3,5.8,5.8",

            "5.8,,6.8,,",
            ",,7.8,,",
            "6.8,0.8,7.8,,",
            "8.3,0.8,6.8,1.3,1.8",
            "8.3,5.8,,1.3,",
            ""
        ])

    #@ordered
    def test_logcsv__reopen3label7value_add5label5value__delta(self):
        labels = ["sens0", "sens1", "sens2", "sens3", "sens4"]
        csv_file = "test_logcsv__reopen3label7value_add5label5value__delta"

        self.open_db(
                labels,
                restore_from="test_logcsv__create3label_add7value__delta",
                log_delta=True)
        self.append_data(labels, 5)
        self.close_db(store_to=csv_file)

        self.assertEqual(
            self.get_csv_content(csv_file), [
            "logdbcsv,version=1.0,delta=1",
            "sens0,sens1,sens2,sens3,sens4",
            "5.8,n,6.8",
            "n,,7.8",
            "6.8,0.8,",
            "8.3,,6.8",
            ",5.8,n",
            ",,",
            "0.3,,5.8",

            "5.8,n,6.8,n,n",
            "n,,7.8,,",
            "6.8,0.8,,,",
            "8.3,,6.8,1.3,1.8",
            ",5.8,n,,n",
            ""
        ])


def help():
    print("Test debug and variations:")
    print("  python test_logdb.py [-h|-help] [-debug <Test>]")
    print("\nStandard Unit test options:")
    sys.argv = [sys.argv[0], "-h"]
    unittest.main()

if __name__ == '__main__':
    argv = sys.argv
    debug_test = None
    while len(argv) > 1:
        argv = argv[1:]
        if argv[0] in ("-h", "-help"):
            help()
        elif argv[0] == "-debug":
            argv = argv[1:]
            debug_test = argv[0]
            LogDbTestClass.DEBUG = True
    
    if debug_test is not None:
        tc = LogDbTestClass()
        tc.setUp()
        #tc.test_5_open_add_extension_to_2x5()
        getattr(tc, debug_test)()
    else:
        unittest.util._MAX_LENGTH=2000
        unittest.TestLoader.sortTestMethodsUsing = test_order_compare
        unittest.main()
