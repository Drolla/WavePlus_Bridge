#!/usr/bin/env python3

##########################################################################
# Airthings Wave Plus Bridge to Wifi/LAN
##########################################################################
# waveplus_bridge.py - Wave Plus Bridge main program
# 
# This file implements the following features of the Wave Plus Bridge:
# 
#   * Sensor scan of one or multiple Wave Plus devices in a user definable
#     interval
#   * HTTP web server to expose the sensor data as HTML web page and as JSON 
#   * string
#   * CSV logging of the sensor data
#
# See the file "README.md" for details about installing, configuring and 
# running this program.
##########################################################################
# Copyright (C) 2020 Andreas Drollinger
# Portions Copyright (c) 2018 Airthings
# See the file "LICENSE" for information on usage and redistribution of this 
# file, and for a DISCLAIMER OF ALL WARRANTIES.
##########################################################################


# Module imports

import sys
import time
import os
import os.path
import re
import struct
import argparse
import yaml
import json
import fnmatch
from http.server import BaseHTTPRequestHandler
import urllib
try:
    from bluepy.btle import UUID, Peripheral, Scanner, DefaultDelegate
except:
    pass
from libs.threadedhttpserver import ThreadedHTTPServer
import libs.logdb as logdb
try:
    import tests.waveplus_emulation as waveplus_emulation
except:
    pass

assert sys.version_info >= (3, 0, 0), "Python 3.x required to run this program"

#############################################
# Argument and Configuration handling
#############################################

class ReadConfiguration:
    """
    Class to handle the configuration of the Wave Plus Bridge.
    Reads the configuration provided as command line arguments, and completes 
    them by definitions provided by Yaml files.
    The configuration is held in form of a dictionary.
    """

    def __init__(self):
        """
        Reads the configuration provided as command line arguments, and 
        completes them by definitions provided by Yaml files.
        """
        
        # Read the configuration from the command line arguments
        config= vars(self.parse_arguments())
        config["graph_decimations"] = None

        # Complete the configurations with the ones defined by the Yaml file
        if config['config'] is not None:
            for key, value in \
                    self.read_yaml_config_file(config['config']).items():
                if config[key] is None or \
                   (type(config[key]) is list and len(config[key]) == 0):
                    config[key] = value

        # Apply some default configuration
        for key, value in {
                "period": str(120),
                "data_retention": str(31*24*3600) # 31 days
        }.items():
            if config[key] is None:
                config[key] = value
        
        # Split the serial number definitions into the real serial numbers and
        # device names: 2931234567, cellar -> sn=2931234567, name=cellar
        sn_defs = config['sn']
        config['sn'] = []
        config['name'] = {}
        for sn_def in sn_defs:
            m = re.match(r'\s*(\w*)[\s,:;]*(.*)', str(sn_def))
            sn = m.group(1)
            name = m.group(2) if m.lastindex==2 else sn
            config['sn'].append(sn)
            config['name'][sn] = name

        # Check the availability and correctness of the serial numbers
        assert (len(config['sn']) != 0), "No serial number provided"
        for sn in config['sn']:
            assert (len(sn) == 10 and sn.isdigit()), "Invalid SN format: " + sn

        self.__dict__ = config

    def read_yaml_config_file(self, file):
        """
        Reads a YAML configuration file. Ignores non existing files.
        """

        # Ignore non existing files
        if file is None:
            return {}
        file = os.path.expanduser(file)
        if not os.path.exists(file):
            return {}
        print("Read configuration file", file)
        
        # Read the file
        with open(file, "r") as yamlfile:
            cfg = yaml.load(yamlfile, Loader=yaml.SafeLoader)
        return cfg

    def parse_arguments(self):
        """
        Parses the command line arguments
        """
        
        parser = argparse.ArgumentParser(
                description="Wave Plus to Wifi/LAN Bridge")
        parser.add_argument(
                "--period",
                help="time in seconds between reading the sensor values")
        parser.add_argument(
                "--data_retention",
                help="data retention time in seconds")
        parser.add_argument(
                "sn", metavar="sn", type=str, nargs="*",
                help="""10-digit serial number of a Wave Plus device (see under
                        the magnetic backplate. This number can be combined 
                        with a device nickname, separated by a column from the 
                        serial number ("2931234567, my_office")""")
        parser.add_argument("--port",
                help="Port of the HTTP web server")
        parser.add_argument("--csv",
                help="CSV file to store data")
        parser.add_argument("--log",
                help="Log file. If not specified the stdout is used")
        parser.add_argument("--config",
                help="YAML configuration file")
        parser.add_argument("--emulation", action='store_true', default=None,
                help="""Emulates the connection with a WavePlus device. This allows
                        testing all other features, like data logging, HTTP
                        service, etc.""")
        parser.add_argument("--report_performance",
                action='store_true', default=None,
                help="""Reports the execution time of some tasks, like the CSV
                        file loading, CVS file creation for an HTTP query,
                        etc.""")

        return parser.parse_args()

    def __getitem__(self, key):
        return self.__dict__[key]
    def __repr__(self):
        return repr(self.__dict__)
    def __iter__(self):
        for x in self.__dict__:
            yield x


#############################################
# Performance reporting
#############################################

class PerformanceCheck():
    """
    This class provides the tool to check the performance of tasks, by setting
    a time anchor before the task is executed, and measuring and reporting then
    the time the execution of the task has taken.
    """
    
    # The performance check and report has to be actively activated
    check_active = False
    file = sys.stdout
    
    def __init__(self, task_description):
        if not self.check_active:
            return
        self.start_time = time.time()
        self.task_description = task_description

    def __del__(self):
        if not self.check_active:
            return
        execution_time_ms = 1000*(time.time()-self.start_time)
        print(("Performance check, {}: {:.3f}ms").
               format(self.task_description, execution_time_ms), file=self.file)

#############################################
# Class WavePlus and Sensors
#############################################

# The two classes, WavePlus and Sensors, is provided by Airthings under the 
# MIT licenses. The code has been slightly modified. The original code is
# available here:
#                   https://github.com/Airthings/waveplus-reader
  

class WavePlus():
    def __init__(self, sn, name=""):
        self.periph = None
        self.val_char = None
        self.mac_addr = None
        self.sn = sn
        self.name = name if name != "" else sn
        self.uuid = UUID("b42e2a68-ade7-11e4-89d3-123b93f75cba")
    
    def __del__(self):
        self.disconnect()

    def connect(self):
        # Auto-discover device on first connection
        if (self.mac_addr is None):
            scanner     = Scanner().withDelegate(DefaultDelegate())
            searchCount = 0
            while self.mac_addr is None and searchCount < 50:
                devices      = scanner.scan(0.1) # 0.1 seconds scan period
                searchCount += 1
                for dev in devices:
                    ManuData = dev.getValueText(255)
                    sn = self.parse_serial_number(ManuData)
                    if (sn == self.sn):
                        # Serial number has been found. Stop searching
                        self.mac_addr = dev.addr
                        break
            
            if (self.mac_addr is None):
                print("ERROR: Could not find device", self.sn, file=logf)
                raise ConnectionError("Could not find device " + self.sn)
            else:
                print("Device {0} found, MAC address={1}".format(
                        wp_device.sn, wp_device.mac_addr), file=logf)
        
        # Connect to device
        if (self.periph is None):
            self.periph = Peripheral(self.mac_addr)
        if (self.val_char is None):
            self.val_char = self.periph.getCharacteristics(uuid=self.uuid)[0]
        
    def read(self):
        if (self.val_char is None):
            print("ERROR: Device is not connected:", self.sn, file=logf)
            raise ConnectionError("Device is not connected" + self.sn)
        rawdata = self.val_char.read()
        rawdata = struct.unpack("BBBBHHHHHHHH", rawdata)
        sensors = Sensors()
        sensors.set(rawdata)
        return sensors
    
    def disconnect(self):
        if self.periph is not None:
            self.periph.disconnect()
            self.periph = None
            self.val_char = None

    def parse_serial_number(self, RawHexStr):
        if RawHexStr == "None":
            sn = "Unknown"
        else:
            ManuData = bytearray.fromhex(RawHexStr)
            if (((ManuData[1] << 8) | ManuData[0]) == 0x0334):
                sn = ManuData[2] | (ManuData[3] << 8) \
                   | (ManuData[4] << 16) | (ManuData[5] << 24)
                sn = str(sn)
            else:
                sn = "Unknown"
        return sn


class Sensors():
    def __init__(self):
        self.sensor_version = None
        self.init_sensor_data()

    def init_sensor_data(self):
        self.sensor_data    = {}
        for key in ("humidity", "radon_st", "radon_lt",
                    "temperature", "pressure", "co2", "voc"):
            self.sensor_data[key] = None

    def set(self, rawData):
        self.sensor_version = rawData[0]
        if (self.sensor_version != 1):
            print("ERROR: Unknown sensor version ({0})".format(
                    self.sensor_version), file=logf)
            self.init_sensor_data()
            raise 
        self.sensor_data = {
            "humidity": rawData[1]/2.0,
            "radon_st": self.conv2radon(rawData[4]),
            "radon_lt": self.conv2radon(rawData[5]),
            "temperature": rawData[6]/100.0,
            "pressure": rawData[7]/50.0,
            "co2": rawData[8]*1.0,
            "voc": rawData[9]*1.0
        }
   
    def conv2radon(self, radon_raw):
        """
        Validate or invalidate the radon value.
        """
        
        if 0 <= radon_raw <= 16383:
            return radon_raw
        return  "N/A"

    def get(self):
        return self.sensor_data


#############################################
# HTTP server
#############################################

class HttpRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler class used in combination with the HTTP/Web server. It
    provides the application specific do_GET method that responses in the 
    following way:
       * If path is /: Redirect the browser to /ui/index.html
       * If path is /data: Provide the current sensor data in JSON format.
       * If path starts with /ui/: Provide the content of the related file
    """
    
    # HTTP content type attributes related to specific file types
    CONTENT_TYPES = {
        '.html': "text/html",
        '.js': "application/javascript",
        '.css': "text/css",
        '': "application/octet-stream",
        }
    
    def do_GET(self):
        """
        Handler method for the GET requests.
        """

        # Default HTTP response and content type.
        http_response = 200
        http_content_type ="text/html"

        # If path is '/': Redirect the browser to /ui/index.html
        if self.path == "/":
            http_body = '<head><meta http-equiv="refresh" ' + \
                        'content="0; URL=/ui/index.html" /></head>'

        # If path is /data: Provide the current sensor data in JSON format.
        elif self.path=="/data":
            response_raw_data = {
                "current_time": int(time.time()),
                "devices": all_sensor_data
            }
            http_body = json.dumps(response_raw_data)
            http_content_type ="application/json"

        # If path is /csv: Provide the current sensor data in CSV format.
        elif self.path.startswith("/csv"):
            if "?" in self.path:
                device_pattern = urllib.parse.unquote(self.path.split("?")[1])
                if device_pattern[0:3] == "re=":
                    device_pattern = device_pattern[3:]
                else:
                    # device_pattern = eval(device_pattern, {}, {})
                    device_pattern = [fnmatch.translate(dpat) 
                                          for dpat in device_pattern.split(";")]
            else:
                device_pattern = ".*"

            pc = PerformanceCheck("CSV data creation")
            http_body = ldb.get_csv(
                    device_pattern,
                    section_decimation_definitions=config["graph_decimations"])
            del pc
            http_content_type ="application/csv"

        # If path starts with /ui/: Provide the content of the related file
        elif self.path.startswith("/ui/") and ".." not in self.path:
            try:
                file_name, file_extension = os.path.splitext(self.path)
                if file_extension not in self.CONTENT_TYPES:
                    file_extension = ""
                http_content_type = self.CONTENT_TYPES[file_extension]
                
                f = open(os.path.dirname(os.path.abspath(__file__)) + os.sep + 
                                         self.path)
                http_body = f.read()
                f.close()
            except IOError:
                http_response = 404
                http_body = "<h1>404 - File not found</h1>"

        # Debug support - allow executing commands
        elif self.path.startswith("/eval") and "?" in self.path:
            try:
                py_function = urllib.parse.unquote(self.path.split("?")[1])
                py_result = eval(py_function)
                http_body = "Result:<br>" + str(py_result)
            except Exception as err:
                http_body = "Error:<br>" + str(err)
                

        # Any other requests are invalid
        else:
            http_response = 404
            http_body = "<h1>404 - Not found</h1>" + \
                        "<p>Allowed requests: /data, /ui/File</p>"

        # Form the full response
        self.send_response(http_response)
        self.send_header("Content-type", http_content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(bytes(http_body, "utf8"))

    # Redefine the log_message method to suppress logging information.
    def log_message(self, format, *args):
        pass


#############################################
# Main
#############################################

if __name__ == "__main__":

    # Read and print the configuration
    try:
        config = ReadConfiguration()
    except AssertionError as err:
        print("ERROR:", err)
        sys.exit(1)
    
    # Check that the bluepy module could be loaded if the application does not
    # run in emulated mode
    assert "bluepy" in sys.modules or config.emulation

    # Define the log output
    logf = sys.stdout
    if config.log is not None and config.log != "":
        try:
            logf = open(config.log, "a", 1)
            print("Logfile:", config.log)
            print("Configuration:", config, file=logf)
        except PermissionError:
            print("No permission to open file", config.log, "use stdout instead")
        except:
            print("Unable to log to file", config.log, "use stdout instead")

    # Enable performance check if requested
    if config.report_performance:
        PerformanceCheck.check_active = True
        PerformanceCheck.file = logf

    # Data logging, optionally into a CSV file
    try:
        log_labels = ["humidity", "radon_st", "radon_lt",
                      "temperature", "pressure", "co2", "voc"]
        pc = PerformanceCheck("CSV file loading")
        ldb=logdb.LogDB(
                {config.name[sn]:log_labels for sn in config.sn},
                config.csv,
                number_retention_records=config.data_retention/config.period)
        del pc
        print("Data are logged to CSV file", config.csv, file=logf)
    except PermissionError:
        print("No permission to open file", config.csv, file=logf)
    except Exception as err:
        print("Error accessing CSV file", config.csv, ":", err, file=logf)
        if logf != sys.stdout:
            print("Error accessing CSV file", config.csv, ":", err,
                    file=sys.stderr)
        sys.exit(1)

    # Start the HTTP web server
    if config.port is not None:
        try:
            server = ThreadedHTTPServer(
                    ("", int(config.port)), HttpRequestHandler)
            print("HTTP/Web server started on port", config.port, file=logf)
        except:
            print("Unable to open HTTP port", config.port, file=logf)
            sys.exit(1)

    # Initialize the access to all Wave Plus devices
    wp_devices = []
    all_sensor_data = {}

    for sn in config.sn:
        if not config.emulation:
            wp_device = WavePlus(sn, config.name[sn])
        else:
            wp_device = waveplus_emulation.WavePlus(sn, config.name[sn])
        wp_devices.append(wp_device)

    # Main loop
    print("Press ctrl+C to exit program!", file=logf)
    iteration_start_time = time.time()
    if config.emulation:
        nbr_pre_emulated = config.data_retention/config.period
        if len(ldb.data["Time"]) < nbr_pre_emulated:
            iteration_start_time -= \
                    (nbr_pre_emulated-len(ldb.data["Time"]))*config.period
    while True:
        try:
            sensor_data = {}
            for wp_device in wp_devices:
                try:
                    # read values
                    wp_device.connect()
                    sensors = wp_device.read()
                    sdata = sensors.get()
                    wp_device.disconnect()
                
                    # Store result
                    sensor_data[wp_device.name] = sdata.copy()
                    sdata["update_time"] = int(time.time())
                    all_sensor_data[wp_device.name] = sdata

                except Exception as err:
                    print("Failed to communicate with device", wp_device.sn,
                            "/", wp_device.name, ":", err, file=logf)

            # Store data in log database
            try:
                ldb.insert(sensor_data, tstamp=int(iteration_start_time))
            except Exception as err:
                print("Failed to log the data:", err, file=logf)

            iteration_start_time += config.period
            if not config.emulation:
                time.sleep(max(0, iteration_start_time - time.time()))
            elif len(ldb.data["Time"])>nbr_pre_emulated:
                time.sleep(max(0, iteration_start_time - time.time()))
        except KeyboardInterrupt:
            break
        except Exception as err:
            print("Error:", err, file=logf)
            pass

    # Close connections and open files
    for wp_device in wp_devices:
        del wp_device
    print("WavePlus_bridge ended", file=logf)
    if config.log is not None:
        del logf
