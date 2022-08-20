"""Logging database

This file implements a logging database optimized to store sequential
data provided for example by sensors. The data is stored in the CSV
format. A definable portion of the data is kept in the RAM to provide
them in a fast way if requested.

Copyright (C) 2020 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import os
import time
import re
import array
import logging

logger = logging.getLogger(__name__)


class _LogDbCsv:
    """CSV logging database base class.

    If the CSV file does not exist, the it is created, an info line
    written to the first line andall labels into the second line. If
    the file exists, it reads the info line and the existing labels.
    If new labels exists, the existing ones are combined with the new
    ones and the combined list written into the header line of the CSV
    file. If the info line is not recognized, the current CSV file is
    backed up and a new one is created.

    The data can be written in 2 modes to the CSV file. In standard
    mode (log_delta=False), each data set is written as independent
    data set to the file. Each CSV file line is therefore
    self-contained. In the second mode only differences from the
    previous data set are written to the file. Depending the nature of
    the data, the CSV file size can be reduced with this mode. Once the
    mode of the CSV file is defined, it will be maintained and a
    mismatch with the log_delta parameter of the constructor will be
    reported with a warning.

    Args:
        labels (list of str): Label list
        file (str): CSV file
        log_delta (bool): Enables delta logging if True.
            Default=False.
    """

    # Python string encoding
    ENCODING = "utf-8"

    # Initial size of the label line
    CSV_HEADER_ROW_LENGTH = 2048

    # Initial file chunk load size that is dynamically increased
    INIT_RELOAD_SIZE = 1000000

    _NAN = float('nan')
    _REP = float('inf')

    def __init__(self, labels, file, log_delta=False):
        logger.debug("_LogDbCsv, Init (file=%s, Labels=%s)", file, labels)

        # Open the file if it exists and read the info line (1st line)
        # and the existing labels (2nd row)
        existing_labels = []
        if os.path.exists(file):
            f = open(file, "br+")
            f.seek(0, 0)
            file_info = str(f.readline(), self.ENCODING).strip().split(",")
            line = str(f.readline(), self.ENCODING)
            header_length = f.tell()
            for label in line.split(","):
                label = label.strip()
                existing_labels.append(label)
            logger.debug("  Header_length: %s", header_length)
            logger.debug("  File info: %s", file_info)

            # Check the consistency of the file info. If it is wrong,
            # rename the file to create a new one
            if len(file_info) != 3 or file_info[0] != "logdbcsv" or \
                    re.fullmatch("delta=[01]", file_info[2]) is None:
                logger.error("LogDbCsv: Incorrect CSV header line in file '" +
                             file + "': '" + ",".join(file_info) +
                             "'. Backup existing file and create new one!")
                f.close()
                os.rename(file, file + time.strftime(
                        "%Y%m%d_%H%M%S", time.localtime(time.time())))
            else:
                # Select the mode from the existing file (delta=0/1)
                existing_log_delta = \
                        {"0": False, "1": True}[file_info[2].split("=")[1]]
                if log_delta != existing_log_delta:
                    logger.error("LogDbCsv: Specified log_delta parameter (%s)"
                                 "does not match with the existing one of file"
                                 "'%s'. Using the existing one!",
                                 log_delta, file)
                    log_delta = existing_log_delta

        # Create the file if it does not exist
        if not os.path.exists(file):
            f = open(file, "bw")
            logger.debug("  New file!")
            header_length = None

        # Create a list of all labels, and another one of the new labels
        all_labels = existing_labels.copy()
        new_labels = []
        for label in labels:
            if label in existing_labels:
                continue
            new_labels.append(label)
            all_labels.append(label)

        logger.debug("  Existing labels: %s", existing_labels)
        logger.debug("  New labels: %s", new_labels)
        logger.debug("  All labels: %s", all_labels)

        # Write the updated CSV header lines with the additional labels
        if len(new_labels) > 0:
            f.seek(0, 0)

            # File information line
            file_info_line = "logdbcsv,version=1.0,delta=" + \
                             ["0", "1"][log_delta]
            f.write(file_info_line.encode())
            f.write(b"\n")

            # Label line
            label_line = ",".join(all_labels)
            label_line += " "*(self.CSV_HEADER_ROW_LENGTH -
                               len(label_line) - len(file_info_line))
            f.write(label_line.encode())
            f.write(b"\n")
            f.flush()

        # Move the write pointer to the file end
        f.seek(0, 2)
        self.labels = all_labels
        self.log_delta = log_delta
        self.f = f
        self.header_length = header_length
        self.last_data_set = {}

    def get_labels(self):
        """Returns the list of all labels."""

        return self.labels

    def _str2float(self, string):
        """Translates a CSV file value into a Python value."""

        try:
            if string == "":
                value = self._REP if self.log_delta else self._NAN
            elif string == "n":
                value = self._NAN
            else:
                value = float(string)
        except Exception:
            if string.strip() == "" and self.log_delta:
                value = self._REP
            else:
                value = self._NAN
        return value

    def restore_data(self, data=None, number_retention_records=None):
        """Restores the data from the CSV file.

        This method restores data from the CSV file either in the data
        structure provided by the parameter 'data', or if this one is
        None, to a newly created data structure.

        Args:
            data (list of arrays): Optionally provided data structure
                where the data has to be restored. Default: None.
            number_retention_records:
                Optional maximum number of data records to load to reduce the
                memory footprint.

        Return:
            list of arrays: Data structure
        """

        # Create the data structure if not provided. This structure is a
        # dictionary of arrays. Use 'double' as array type.
        if data is None:
            data = {}
            for label in self.labels:
                data[label] = array.array("d")

        # Skip data restore if the CSV file is new
        if self.header_length is None:
            return data

        f = self.f

        # Organize the data arrays as list to improve access speed.
        # Ignore labels that have no member in the data dictionary.
        data_matrix = []
        for label in self.labels:
            data_matrix.append(data[label] if label in data else None)

        # Get the current file size
        f.seek(0, 2)
        file_size = f.tell()
        logger.debug("  Load existing data, file size: %s", file_size)

        # Read the file by chunks, starting at the file end. The chunk
        #  size is defined by 'reload_size' that is will be increased.
        # The data arrays are created in the inverse sense; elements 0
        # are the last elements stored in the CSV file. After reading
        # all data the arrays are reversed.
        read_pos = file_size
        reload_size = self.INIT_RELOAD_SIZE
        all_read = False
        nbr_records_to_load = float('inf') if number_retention_records is None\
                                           else number_retention_records
        while not all_read:
            # Limit the number of records to load if required
            if nbr_records_to_load <= 0:
                break

            # Set the read position to the new location. Ensure that the
            # header line is not read
            if read_pos-reload_size < self.header_length:
                f.seek(self.header_length-2, 0)
                all_read = True
            else:
                f.seek(read_pos-reload_size, 0)

            # From the defined read position, go to the next line start,
            # and adjust the exact read chunk size and read position.
            f.readline()
            read_size = read_pos - f.tell()
            read_pos = f.tell()
            logger.debug("    Load %s bytes from position %s",
                         read_size, read_pos)

            # Read the data chunk
            data_csv = f.read(read_size)
            logger.debug("    Read %s lines", data_csv.count(b"\n"))

            # Handle each line of the CSV file in the inversed sense.
            # Add the data in this inversed sense to the data arrays.
            for line in reversed(data_csv.split(b"\n")):
                # Strip removes eventual \r characters at the line end
                data_record = str(line, self.ENCODING).strip().split(",")

                # Skip the line if it is empty, and raise an error if
                # the number of data words in the line are higher than
                # the number of defined labels.
                if len(data_record) < 2:
                    continue
                if len(data_record) > len(data_matrix):
                    raise Exception("LogDbCVS, restore_data: Line with " +
                                    "more than {} values: {!a}").format(
                                    len(data_record), str(line, self.ENCODING))

                # Add the data of the line to the data arrays
                for index, data_item in enumerate(data_record):
                    if data_matrix[index] is None:
                        continue
                    data_matrix[index].append(self._str2float(data_item))

                # Fill up eventual missing data values with NANs
                for index in range(len(data_record), len(self.labels)):
                    if data_matrix[index] is None:
                        continue
                    data_matrix[index].append(self._NAN)

                # Limit the number of records to load if required
                nbr_records_to_load -= 1
                if nbr_records_to_load <= 0:
                    break

            # Increase the reload chunk size
            reload_size *= 2

        # Reverse all data arrays. If only deltas are logged, populate
        # the data values to the repeated locations
        for ds in data_matrix:
            if ds is not None:
                ds.reverse()
                if self.log_delta:
                    value = self._NAN
                    for index in range(len(ds)):
                        if ds[index] == self._REP:
                            ds[index] = value
                        else:
                            value = ds[index]

        # Move the write pointer to the file end
        f.seek(0, 2)

        # That's it. Return the created data structure
        logger.debug(" %s data records read (+ header line)",
                     len(data_matrix[0]))
        return data

    def __del__(self):
        """ Closes the open CSV file"""

        try:
            self.f.close()
        except Exception:
            pass

    def insert(self, data_set):
        """Inserts a new data set.

        Writes a new data set to the CSV file.

        Args:
            data_set (dictionary): Data set to store in the CSV file.

        Return:
            -
        """

        logger.debug("_LogDbCsv - insert: %s", data_set)

        # Write the data set as new row to the CSV file: Loop over all
        # defined labels and get the respective value from the provided
        # data set dictionary. If the value is not defined, set it to
        # NA. Handle the two logging modes (log_delta=0,1).
        csv_data = []
        for index, label in enumerate(self.labels):
            value = self._NAN if label not in data_set or \
                                 data_set[label] == "" else data_set[label]

            # Normal (not delta log)
            if not self.log_delta:
                csv_data.append(str(value) if value == value else "")

            # Delta log: Store value in function of the previous value
            else:
                # Delta log, no previous value is available
                if label not in self.last_data_set:
                    csv_data.append(str(value) if value == value else "n")

                # Delta log, previous value is available
                else:
                    last_value = self.last_data_set[label]

                    # Delta log, new value is not NaN
                    if value == value:
                        csv_data.append("" if value == last_value
                                           else str(value))

                    # Delta log, new value is NaN
                    else:
                        csv_data.append("n" if last_value == last_value
                                            else "")

                # Delta log, store the value
                self.last_data_set[label] = value

        # Write the line and flush the new data
        self.f.write(str.encode(",".join(csv_data)))
        self.f.write(b"\n")
        self.f.flush()


class LogDB:
    """Logging database class.

    This class provides a logging database to log sequential data sets,
    like data provided in a regular interval by sensors. An in-memory
    database will be created that has the form of a list of arrays. To
    keep the size of this in-memory database limited, either the number
    of retention records or the retention time (duration) can be
    specified.

    Optionally, a logging file can be defined. If it is defined and the
    file exists its contained data is restored into the memory (by
    respecting the above explained retention constraints). And if the
    file does not exist it is created and the labels added to the
    header file.

    The data can be written in 2 modes to the CSV file. In standard
    mode (log_delta=False), each data set is written as independent
    data set to the file. Each CSV file line is therefore
    self-contained. In the second mode only differences from the
    previous data set are written to the file. Depending the nature of
    the data, the CSV file size can with this mode.

    The labels can be specified in different ways:
        List of str: ["temperature", "humidity", "pressure"]
        Dictionary of list of str:
            {"living": ["temperature", "humidity"],
             "office": ["temperature", "humidity", "pressure"]}

    Args:
        label_specs (see above): Label specifications
        file (str): CSV file
        number_retention_records (bool): Number of data records to
            retain. Default: None (no constraint).
        retention_time (float): Time in seconds to retain the data.
            Default: None (no constraint).
        log_delta (bool): Enables delta logging if True. Default=False.
    """

    # Python string encoding
    ENCODING = "utf-8"

    _NAN = float('nan')

    def __init__(self, label_specs, file=None,
                 number_retention_records=None, retention_time=None,
                 log_delta=False):
        logger.info("LogDB, Init (file=%s, label=%s)", file, label_specs)

        # Create the label list. The first label is always "Time". If
        # the label are specified as a dictionary of list, then the
        # label names are composed by the dictionary key and the label
        # list element, separated by ':' (e.g. "living:temperature",
        # "office:pressure").
        labels = ["Time"]
        if isinstance(label_specs, dict):
            for main_label, sub_labels in label_specs.items():
                for sub_label in sub_labels:
                    labels.append(main_label + ":" + sub_label)
        else:
            for label in label_specs:
                labels.append(label)
        logger.debug("  Labels: %s", labels)

        # Create the data structure (list of arrays of doubles)
        data = {}
        for label in labels:
            data[label] = array.array("d")

        # Open the CSV file, restore the data if it exists already
        logdbcsv = None
        if file is not None:
            logdbcsv = _LogDbCsv(labels, file, log_delta=log_delta)
            logdbcsv.restore_data(data, number_retention_records)

        self.labels = labels
        self.logdbcsv = logdbcsv
        self.data = data
        self.number_retention_records = number_retention_records
        self.retention_time = retention_time

    def __del__(self):
        """Closes the CSV file"""

        if self.logdbcsv is not None:
            del self.logdbcsv

    def insert(self, log_data, tstamp=None):
        """Inserts a new data set.

        Writes a new data set to the in-memory database and if defined
        also to the CSV file. If the in-memory database has been size
        constrained, its size is reduced each time it exceeds 10% of
        the constraint.

        The data set can be defined in different ways:
            List of float: The number and order of the values has to
                           correspond to the defined labels. Example:
                           [23.1, 57.1, 894.1]
            Dictionary of float:
                           Values can be provided for either all labels
                           or just for some of them. Example:
                           {"temperature": 23.1, "humidity": 57.1}
            Dictionary of dictionary of float:
                           Values can be provided for either all labels
                           or just for some of them. Example:
                           {"living": {"temperature": 23.1,
                                       "humidity": 57.1},
                            "office": {"temperature": 24.1,
                                       "pressure": 976}}

        Args:
            log_data (see above): Data set to store
            tstamp (int or float): Time stamp value. If not defined the
                current time is used.

        Return:
            -
        """

        logger.debug("LogDB - insert: %s", log_data)
        if tstamp is None:
            tstamp = int(time.time())

        # Create the data set that has a form of a simply dictionary
        # {label_1: value_1, label_2: value_2}
        data_set = {"Time": tstamp}
        if isinstance(log_data, list):
            assert len(log_data) == len(self.labels)-1, \
                  "{}.log: Got {} data words for {} defined labels!".format(
                  self.__class__.__name__, len(log_data), len(self.labels))
            for index, label in enumerate(self.labels[1:]):
                data_set[label] = log_data[index]
        elif isinstance(log_data, dict):
            for d_key, d_value in log_data.items():
                if isinstance(d_value, dict):
                    for d_key2, d_value2 in d_value.items():
                        data_set[d_key+":"+d_key2] = d_value2
                else:
                    data_set[d_key] = d_value
            assert len(data_set) <= len(self.labels), \
                    "{}.log: Got {} data words for {} defined labels!".format(
                    self.__class__.__name__, len(data_set), len(self.labels))
        else:
            assert False, \
                  "data set format unknown: {}".format(log_data.__class__)

        logger.debug("  data_set: %s", data_set)

        # Register the data set in the CSV database
        if self.logdbcsv is not None:
            self.logdbcsv.insert(data_set)

        # Register the data set in the in-memory database
        for label in self.labels:
            self.data[label].append(
                data_set[label] if label in data_set else self._NAN)

        # Limit the in-memory data if constraints are defined. To reduce
        # CPU time, perform this data limitation only if the data
        # exceeds 10% of the specified limit.
        nbr_rec_to_delete = 0
        if self.number_retention_records is not None and \
                len(self.data["Time"]) > self.number_retention_records*1.1:
            nbr_rec_to_delete = len(self.data["Time"]) - \
                                self.number_retention_records
        if self.retention_time is not None:
            while nbr_rec_to_delete < len(self.data["Time"]) and \
                    self.data["Time"][nbr_rec_to_delete] < \
                    tstamp - self.retention_time*1.1:
                nbr_rec_to_delete += 1
        if nbr_rec_to_delete > 0:
            for label in self.labels:
                self.data[label] = self.data[label][nbr_rec_to_delete:]

    def get_labels_from_spec(self, label_specs):
        """Get a label list from label specifications.

        Args:
            label_specs: Label specifications (see below)

        Return:
            Label list

        'label_specs' allow selecting the labels in multiple manners:
            str: single regular expression string.
                Example: ".*:temperature"
            list of str: List of regular expression strings.
                Example: [".*:temperature", ".*:humidity"]
            dict of str: Dictionary of regular expression strings.
                Example: {"living": "temp.*", "office": "hum.*"]
            dict of list of str: Dictionary of lists of regular
                expression strings. Example: {
                    "living": ["temp.*", "hum.*"],
                    "office": ["temp.*", "co2", "voc"]}
        """

        logger.debug("LogDB - get_labels_from_spec: %s", label_specs)
        csv_file_data = []

        # Create a list of re-compiled key patterns, based on the
        # provided key specs. Create first the un-compiled list
        key_patterns = []
        if isinstance(label_specs, str):
            key_patterns.append(label_specs)
        elif isinstance(label_specs, list):
            for key_spec in label_specs:
                key_patterns.append(key_spec)
        elif isinstance(label_specs, dict):
            for prefix, sub_label_specs in label_specs.items():
                if isinstance(sub_label_specs, list):
                    for sub_key_spec in sub_label_specs:
                        key_patterns.append(prefix + ":" + sub_key_spec)
                elif isinstance(sub_label_specs, str):
                    key_patterns.append(prefix + ":" + sub_label_specs)
        # And compile finally the key list
        for index, key_pattern in enumerate(key_patterns):
            try:
                key_patterns[index] = re.compile(key_pattern)
            except Exception:
                raise Exception("Unable to handle regular expression '" +
                                str(key_pattern) + "'")

        # Create the label list. The first element is the time stamp
        labels = ["Time"]
        for key_pattern in key_patterns:
            for label in self.labels[1:]:
                if key_pattern.fullmatch(label) is not None:
                    labels.append(label)
        return labels

    @staticmethod
    def get_abs_index(position, index_range):
        """Get the absolute position index in a certain range.

        This method is used by other methods to create absolute indexes
        based on provided relative positions and index ranges that
        define start and end indexes. The relative position can be
        provided as an absolute or a normalized distance relative to
        the start or end index.

        Args:
            position (positive or negative int or float):
                If positive: Distance is relative to the start index.
                If negative: Distance is relative to the end index.
                If int: Distance is absolute.
                If float: Distance is normalized to the span between
                    the start and the end indexes.
            index_range (2-element list of int): List representing the
                absolute start and end indexes.

        Example: For index_range=[100,200] all the following positions
            are equivalent, and get_abs_index returns 130:
            position = 30, -70, 0.3, -0.7

        Return:
            int: Absolute position index
        """

        ref_index = (index_range[0] if position >= 0 else index_range[1])
        if isinstance(position, int):
            return int(ref_index + position)
        elif isinstance(position, float):
            return int(ref_index + position*(index_range[1]-index_range[0]))
        else:
            raise Exception("get_abs_index: type of position is " +
                            type(get_abs_index))

    def get_index_range(self, start=0.0, end=1.0):
        """Get the index range

        Args:
            start (int or float): Start position (see below)
            end (int or float): End position (see below)

        Return:
            Absolute index range (list of begin and end index)

        The start and end indexes cover by default all the data stored
        in the memory that may have been limited with the parameter
        'number_retention_records'. This range can be overridden with
        the 'start' and 'end' parameters that allow defining relative
        positions to the default start and end index (see method
        'get_abs_index').

        Example: For number_retention_records=1000, all the following
            start/end definitions select the same range between indexes
            250 and 750:
                start,end = 250,-250; -750,750; 0.25,-0.25; -0.75,0.75
        """

        # Get the full index range
        length = len(self.data["Time"])
        index_range = [
            0 if self.number_retention_records is None or
                 length < self.number_retention_records
              else length-self.number_retention_records,
            length]

        # Apply the index range restrictions
        index_range = [
            self.get_abs_index(start, index_range),
            self.get_abs_index(end, index_range)]

        return index_range

    def get_nbr_active_records(self):
        """Get the number of records stored in the RAM
        """

        return len(self.data["Time"])

    def get_csv(self, label_specs=".*",
                start=0.0, end=1.0, section_decimation_definitions=None):
        """Get data in CSV format.

        Get the data selected by 'label_specs', 'start' and 'end' in
        CSV format. Optionally, sections can be defined in which the
        data is grouped and averaged.

        Args:
            label_specs: Label specifications (see method
                'get_labels_from_spec'). Default=".*" (all labels
                selected).
            start (int or float): Start position (see below)
            end (int or float): End position (see below)
            section_decimation_definitions (see below): Data grouping
                definitions

        Return:
            -

        The absolute start and end index are evaluated by the method
        'get_index_range' that take as argument the 'start' and 'end'
        parameters.

        The data can be section wise decimated to reduce the CSV data
        size. It is for example possible to keep the data from the past
        24 hours undecimated, to decimate the data of the past week by
        a certain factor (e.g. 3), and to decimate the data of the past
        month by another factor (e.g. 8).

        The section_decimation_definitions parameter is a dictionary of
        positions where a new decimation factor has to be applied. The
        default decimation factor is initialized to 1 (no decimation).
        Then, the data is read from the oldest to the newest one. Each
        time a section decimation definition is reached, the
        corresponding new decimation factor is applied. Similar to the
        definition of the start and end positions, section positions
        are also defined relative to the effective start and end index
        using the method 'get_abs_index'.

        Example: Decimation by 8 of the oldest 80% of data, by a factor
            of 3 of the 10% second newest data, and a factor of 1 of the
            newest data:
            section_decimation_definitions = {0%:8, 0.8:3, 0.9:1}
        """

        logger.debug("LogDB - get_csv: %s", label_specs)
        csv_file_data = []

        # Get the label list and create an index list
        labels = self.get_labels_from_spec(label_specs)
        data_matrix = []
        for label in labels:
            data_matrix.append(
                            self.data[label] if label in self.data else None)

        # Get the constrained index range
        index_range = self.get_index_range(start, end)

        # Process the section decimation specification
        length = len(data_matrix[0])
        section_starts = []
        pos_def_2_index = {}
        if section_decimation_definitions is not None:
            for position in section_decimation_definitions:
                section_start = self.get_abs_index(position, index_range)
                section_starts.append(section_start)
                pos_def_2_index[section_start] = position
        section_starts.append(length)
        section_start = section_starts.pop(0)
        decimation_factor = 1

        # Write the header
        csv_file_data.append(",".join(labels))

        # Write the data
        for pos in range(*index_range):
            if pos % decimation_factor == 0:
                sum_values = [0] * (len(data_matrix)-1)
                sum_length = sum_values.copy()
            for data_index, data_array in enumerate(data_matrix[1:]):
                if data_array[pos] == data_array[pos]:
                    sum_values[data_index] += data_array[pos]
                    sum_length[data_index] += 1
            if (pos+1) % decimation_factor == 0:
                csv_line_data = [time.strftime(
                        "%Y/%m/%d %H:%M", time.localtime(data_matrix[0][pos]))]
                for data_index, data_array in enumerate(data_matrix[1:]):
                    if sum_values[data_index] == sum_values[data_index] and \
                            sum_length[data_index] > 0:
                        data_avg = \
                                sum_values[data_index]/sum_length[data_index]
                        csv_line_data.append(
                              format(data_avg, ".2f").rstrip("0").rstrip("."))
                    else:
                        csv_line_data.append("")
                csv_file_data.append(",".join(csv_line_data))

                if pos > section_start:
                    decimation_factor = section_decimation_definitions[
                                        pos_def_2_index[section_start]]
                    section_start = section_starts.pop(0)

        return "\n".join(csv_file_data)

    def get(self, label_specs=".*", start=0.0, end=1.0):
        """Get the in-memory stored data list of dictionaries.

        Args:
            label_specs: Label specifications (see method
                'get_labels_from_spec'). Default=".*" (all labels
                selected).
            start (int or float): Start position (see below)
            end (int or float): End position (see below)

        Return:
            -

        The absolute start and end index are evaluated by the method
        'get_index_range' that take as argument the 'start' and 'end'
        parameters.
        """

        logger.debug("LogDB - get:")

        # Get the label list and constrained index range
        labels = self.get_labels_from_spec(label_specs)
        index_range = self.get_index_range(start, end)

        # Generate all data sets
        data_sets = []
        for pos in range(index_range[0], index_range[1]):
            data_set = {}
            for label in labels:
                if label not in self.data:
                    continue
                data_word = self.data[label][pos]
                if data_word == data_word:
                    data_set[label] = data_word
            data_sets.append(data_set)
            logger.debug("  %s", data_set)

        return data_sets
