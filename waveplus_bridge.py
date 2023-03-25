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
#   * HTTP web server to expose the sensor data as HTML web page and in JSON
#   * format
#   * CSV logging of the sensor data
#   * Configurable email alerts
#
# See the file "README.md" for details about installing, configuring and
# running this program.
##########################################################################
# Copyright (C) 2020-2022 Andreas Drollinger
# See the file "LICENSE" for information on usage and redistribution of this
# file, and for a DISCLAIMER OF ALL WARRANTIES.
##########################################################################


# Module imports

import sys
import time
import os
import os.path
import signal
import re
import logging
import logging.config
import argparse
import yaml
import json
import fnmatch
import urllib
from http.server import BaseHTTPRequestHandler
from libs.threadedhttpserver import ThreadedHTTPServer
import libs.logdb as logdb
import libs.trigger as trigger
from libs.threadedsendmail import ThreadedSendMail
from libs.performancecheck import PerformanceCheck
try:
    import libs.waveplus as waveplus
except Exception:
    pass
if os.path.basename(os.getcwd()) == "tests":
    sys.path.append(".")
    import waveplus_emulation as waveplus_emulation
try:
    from libs.threadedmqttpublisher import ThreadedMqttPublisher
except Exception as err:
    print("MQTT service is not available:", err)
assert sys.version_info >= (3, 0, 0), "Python 3.x required to run this program"

logger = logging.getLogger(__name__)


#############################################
# Argument and Configuration handling
#############################################

class ReadConfiguration:
    """Wave Plus Bridge configuration handling

    Reads the configuration provided as command line arguments, and completes
    them by definitions provided by Yaml files.
    The configuration is held in form of a dictionary.
    """

    def __init__(self):
        # Read the configuration from the command line arguments
        config = vars(self.parse_arguments())
        config["graph_decimations"] = None

        # Complete the configurations with the ones defined by the Yaml file
        if config['config'] is not None:
            for key, value in \
                    self.read_yaml_config_file(config['config']).items():
                if key not in config or \
                        config[key] is None or \
                        (type(config[key]) is list and len(config[key]) == 0):
                    config[key] = value

        # Apply some default configuration
        for key, value in {
                "period": 120,
                "retries": 3,
                "retry_delay": 1,
                "data_retention": 31*24*3600,  # 31 days
        }.items():
            if key not in config or config[key] is None:
                config[key] = value

        # Split the serial number definitions into the real serial numbers and
        # device names: 2931234567, cellar -> sn=2931234567, name=cellar
        sn_defs = config['sn']
        config['sn'] = []
        config['name'] = {}
        for sn_def in sn_defs:
            m = re.match(r'\s*(\w*)[\s,:;]*(.*)', str(sn_def))
            sn = m.group(1)
            name = m.group(2) if m.lastindex == 2 else sn
            config['sn'].append(sn)
            config['name'][sn] = name

        # Check the availability and correctness of the serial numbers
        assert (len(config['sn']) != 0), "No serial number provided"
        for sn in config['sn']:
            assert (len(sn) == 10 and sn.isdigit()), "Invalid SN format: " + sn

        self.__dict__ = config

    def read_yaml_config_file(self, file):
        """ Reads a YAML configuration file

        If the configuration file does not exist it returns without generating
        an error.
        """

        # Raise an error if a Yaml config file is defined but not existing
        if file is None:
            return {}
        file = os.path.expanduser(file)
        assert os.path.exists(file), "Configuration file not existing: " + file

        # Read the file
        logger.info("Read configuration file '%s'", file)
        with open(file, "r") as yamlfile:
            cfg = yaml.load(yamlfile, Loader=yaml.SafeLoader)
        return cfg

    def parse_arguments(self):
        """Parses the command line arguments"""

        parser = argparse.ArgumentParser(
                description="Wave Plus to Wifi/LAN Bridge")
        parser.add_argument(
                "--period", type=int,
                help="Time in seconds between reading the sensor values")
        parser.add_argument(
                "--data_retention", type=int,
                help="Data retention time in seconds")
        parser.add_argument(
                "sn", metavar="sn", type=str, nargs="*",
                help="""10-digit serial number of a Wave Plus device (see under
                        the magnetic backplate. This number can be combined
                        with a device nickname, separated by a column from the
                        serial number ("2931234567, my_office")""")
        parser.add_argument(
                "--port", help="Port of the HTTP web server")
        parser.add_argument(
                "--csv", help="CSV file to store data")
        parser.add_argument(
                "--log", help="Log file. If not specified the stdout is used")
        parser.add_argument(
                "--config", help="YAML configuration file")
        parser.add_argument(
                "--emulation", action='store_true', default=None,
                help="""Emulates the connection with a WavePlus device. This
                        allows testing all other features, like data logging,
                        HTTP service, etc.""")

        return parser.parse_args()

    def __getitem__(self, key):
        return self.__dict__[key]

    def __repr__(self):
        return repr(self.__dict__)

    def __iter__(self):
        for x in self.__dict__:
            yield x


#############################################
# HTTP server
#############################################

# Use a factory class to add context to the HTTP request handler.
# See: https://stackoverflow.com/questions/21631799

def ContextSpecificHttpRequestHandler(all_sensor_data_ts, log_database,
                                      graph_decimations):

    class HttpRequestHandler(BaseHTTPRequestHandler):
        """HTTP request handler used for the HTTP/web server

        This HTTP request handler provides the application specific do_GET
        method that responses in the following way:
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
            """Handler method for the GET requests"""

            # Default HTTP response and content type.
            http_response = 200
            http_content_type = "text/html"

            # If path is '/': Redirect the browser to /ui/index.html
            if self.path == "/":
                http_body = '<head><meta http-equiv="refresh" ' + \
                            'content="0; URL=/ui/index.html" /></head>'

            # If path is /data: Provide the current sensor data in JSON format.
            elif self.path == "/data":
                http_content_type, http_body = self.get_sensor_data_json()

            # If path is /csv: Provide the current sensor data in CSV format.
            elif self.path.startswith("/csv"):
                http_content_type, http_body = self.get_sensor_history_csv()

            # If path starts with /ui/: Provide the content of the related file
            elif self.path.startswith("/ui/") and ".." not in self.path:
                try:
                    http_content_type, http_body = self.get_file_content()
                except IOError:
                    http_response = 404
                    http_body = "<h1>404 - File not found</h1>"

            # Debug support - allow executing commands
            elif self.path.startswith("/eval") and "?" in self.path:
                try:
                    http_content_type, http_body = self.get_eval()
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

        def get_sensor_data_json(self):
            """Get all sensor data in JSON format"""

            response_raw_data = {
                "current_time": int(time.time()),
                "devices": all_sensor_data_ts
            }
            return "application/json", json.dumps(response_raw_data)

        def get_sensor_history_csv(self):
            """Get the sensor history in CSV format"""

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

            with PerformanceCheck("HTTP request, provide sensor data"):
                http_body = log_database.get_csv(
                        device_pattern,
                        section_decimation_definitions=graph_decimations)
            return "application/csv", http_body

        def get_file_content(self):
            """Get the content of the specified file"""

            file_name, file_extension = os.path.splitext(self.path)
            if file_extension not in self.CONTENT_TYPES:
                file_extension = ""
            f = open(os.path.dirname(os.path.abspath(__file__)) + os.sep +
                     self.path)
            http_body = f.read()
            f.close()
            return self.CONTENT_TYPES[file_extension], http_body

        def get_eval(self):
            """Evaluate a Python expression"""

            py_function = urllib.parse.unquote(self.path.split("?")[1])
            py_result = eval(py_function)
            return "text/html", "Result:<br>"+str(py_result)

        # Redefine the log_message method to suppress logging information.
        def log_message(self, format, *args):
            pass

    return HttpRequestHandler


#############################################
# Alert actions - print and mail alerts
#############################################

class PrintAction:
    """Print action class

    This class exposes the method 'action' that can be provided to the log
    method of the trigger module.

    Args:
        print_action_config: Configuration dictionary (consult
                waveplus_bridge.yaml or README.md for details)
    """

    def __init__(self, print_action_config):
        self.message = "Sensor alert: Sensor: %d.%s, Level: %v"
        if "message" in print_action_config:
            self.message = print_action_config["message"]

    def action(self, value, device, sensor):
        """Alert action function - prints the specified message"""

        message = self.message.replace("%v", str(value)).replace("%d", device)\
                              .replace("%s", sensor)
        logger.info(message)


class MailAction:
    """Mail alert action class

    This class exposes the method 'action' that can be provided to the log
    method of the trigger module.

    Args:
        smtp_config: SMTP server configuration dictionary
        mail_action_config: Mail action configuration dictionary

    The files waveplus_bridge.yaml and README.md for details, provides
    explanations about the two arguments.
    """

    def __init__(self, smtp_config, mail_action_config):
        # Setup the mail service
        self.alert_mail_service = ThreadedSendMail(
                server=smtp_config["server"],
                port=smtp_config["port"],
                security=smtp_config["security"] if "security" in smtp_config
                                                 else None,
                user=smtp_config["user"] if "user" in smtp_config else None,
                password=smtp_config["password"] if "password" in smtp_config
                                                 else None)

        self.from_ = mail_action_config["from"]
        self.to = mail_action_config["to"]
        self.subject = "Sensor alert"
        self.message = "Sensor: %d.%s, Level: %v"
        if "subject" in mail_action_config:
            self.subject = mail_action_config["subject"]
        if "message" in mail_action_config:
            self.message = mail_action_config["message"]

    def action(self, value, device, sensor):
        """Alert action function - sends a mail alert"""

        message = self.message.replace("%v", str(value)).replace("%d", device)\
                              .replace("%s", sensor)
        self.alert_mail_service.send_mail(
                self.from_, self.to, self.subject, message)


class Actions:
    """Action/alert class

    This class provides an action trigger configurable via the YAML
    configuration file.

    Args:
        smtp_config: SMTP server configuration dictionary
        alerts_config: Alerts configuration dictionary

    The files waveplus_bridge.yaml and README.md provides details about the two
    configuration arguments.
    """

    def __init__(self, smtp_config, alerts_config):
        # Create the list of Trigger instances, one for each defined alert.
        self.sources_trigger_actions_list = []
        for alert_config in (alerts_config if isinstance(alerts_config, list)
                             else [alerts_config]):
            # For each alert, create the list of sources. A source may be
            # defined as a string, or as a list of strings.
            sources = []
            for source in (alert_config["sources"]
                           if isinstance(alert_config["sources"], list)
                           else [alert_config["sources"]]):
                sources.append(source.split(":"))

            # For each alert, create the list of actions. An may be defined as
            # a string, or as a list of strings.
            actions = alert_config["actions"]
            action_functions = []
            for action in actions if isinstance(actions, list) else [actions]:
                # Create the required action instance (mail or print)
                if "mail" in action:
                    action_functions.append(
                            MailAction(smtp_config, action["mail"]).action)
                if "print" in action:
                    action_functions.append(
                            PrintAction(action["print"]).action)

            # Create the trigger instance
            trigger_action = trigger.Trigger(
                    alert_config["trigger"], action_functions)

            # Register the trigger source configuration and trigger action
            # instance
            self.sources_trigger_actions_list.append([sources, trigger_action])

    def check_levels(self, data):
        """Check sensor levels

        This method needs to be called each sensor acquisition period. It loops
        over all defined trigger actions and calls the log function of the
        trigger instance. Beside the sensor value, also the names of the
        related device and sensor are provided to the log function.

        Args:
            data: Sensor data structure of all devices
        """

        error_msg = None
        for sta in self.sources_trigger_actions_list:
            for source in sta[0]:
                # print('  source:', source, file=log_file)
                try:
                    value = data[source[0]][source[1]]
                    sta[1].log(value, source[0], source[1])
                except Exception as err:
                    error_msg = "MailAlerts: Error accessing {}: {}".format(
                            ":".join(source), err)
                    logger.debug(error_msg, exc_info=1)
        if error_msg is not None:
            raise Exception(error_msg)


#############################################
# MQTT publishing
#############################################

class MqttPublisher:
    """MQTT publisher class

    This class manages the optional publishing of the sensor data to an MQTT
    broker.

    Args:
        mqtt_config: MQTT configuration dictionary

    The files waveplus_bridge.yaml and README.md provide explanations about the
    configuration options.
    """

    def __init__(self, config):
        # Store the configuration options and complete them if necessary
        self.cfg_topic = config["topic"] if "topic" in config else ""
        self.cfg_publish = config["publish"]
        self.status_topic = "/".join(filter(bool, [self.cfg_topic, "status"]))
        will = {"topic": self.status_topic, "payload": "Connection lost",
                "retain": True}

        self.mqtt_publisher = ThreadedMqttPublisher(
            hostname=config["host"],
            port=config["port"],
            client_id=config["client_id"] if "client_id" in config else None,
            auth=config["auth"] if "auth" in config else None,
            tls=config["tls"] if "tls" in config else None,
            will=config["will"] if "will" in config else will
        )

        # Wait until the thread is created, and set the status to 'Online'
        time.sleep(1)
        publish_result = self.mqtt_publisher.publish_single(
            topic=self.status_topic, payload="Online", qos=2, retain=True)

    def stop(self):
        """Stops the network thread and the connection

        Call preferably this function to stop the connection instead of
        deleting the object instance to ensure a controlled disconnection.
        Note that the network cannot be restarted.
        """

        # Ignore this command if the mqttc object is already deleted (=None)
        if self.mqtt_publisher is None:
            return

        # Set the master status to 'Offline'
        publish_result = self.mqtt_publisher.publish_single(
            topic=self.status_topic, payload="Offline", qos=2, retain=True)
        publish_result.wait_for_publish()

        # Stop and delete the MQTT publisher
        self.mqtt_publisher.stop()
        del self.mqtt_publisher
        self.mqtt_publisher = None

    def __del__(self):
        self.stop()

    def publish(self, data):
        """Publish updated sensor levels

        This method needs to be called each sensor acquisition period. It loops
        over all sensor data, checks if a sensor value has to be published,
        creates the MQTT message and submits it to an MQTT broker.

        Args:
            data: Sensor data structure of all devices
        """

        # Generation of the list of MQTT messages
        mqtt_messages = []
        for device in data:
            # Check if a device has to be published
            if device in self.cfg_publish:
                sensor_filter = self.cfg_publish[device]
            elif "*" in self.cfg_publish:
                sensor_filter = self.cfg_publish["*"]
            else:
                continue

            # Define the status topic based on the sensor data availability
            mqtt_messages.append({
                "topic": "/".join([device, "status"]),
                "payload": "Online" if data[device] else "Offline",
                "retain": True
            })

            # Add the sensor data
            for sensor in data[device]:
                # Check if a sensor of a device has to be published
                if sensor not in sensor_filter and \
                        "*" not in sensor_filter:
                    continue

                # Extend the existing message with the current sensor data
                mqtt_messages.append({
                    "topic": "/".join([device, sensor]),
                    "payload": data[device][sensor],
                    "retain": True
                })
        mqtt_messages.append({"topic": "publish_time",
                              "payload": int(time.time()),
                              "retain": True})

        # Publish the sensor data to the MQTT broker
        self.mqtt_publisher.publish_multiple(
                mqtt_messages, topic_root=self.cfg_topic)


#############################################
# Main
#############################################

def main():

    # Define and register signal handlers
    def handle_exit(sig, frame):
        raise SystemExit()

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # Read and print the configuration
    try:
        config = ReadConfiguration()
    except AssertionError as err:
        print("Error:", err)
        sys.exit(1)

    # Check that the bluepy module could be loaded if the application does not
    # run in emulated mode
    assert "bluepy" in sys.modules or config.emulation

    # Configure logging
    if isinstance(config.log, dict):
        logging_config = config.log
    else:
        # Define the default configuration for the case no YAML configuration
        # file is provided. Use by default a file handler, otherwise a stream
        # handler. If no port is defined, set the log level of this main
        # application to 'debug'.
        log_level = "DEBUG" if config.port is None else "INFO"
        logging_config = {
            'version': 1,
            'formatters': {'default': {
                'format':
                    '%(asctime)s - %(name)13s[%(levelname)7s] - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'}},
            'loggers': {
                '__main__': {'level': log_level},
                'libs': {'level': 'WARNING'}}
        }
        if config.log is not None and isinstance(config.log, str):
            logging_config.update({
                'root': {'level': 'WARNING', 'handlers': ['file']},
                'handlers': {'file': {
                    'level': 'DEBUG', 'formatter': 'default',
                    'class': 'logging.FileHandler', 'filename': config.log,
                    'encoding': 'utf8', 'mode': 'w'}}
            })
        else:
            logging_config.update({
                'root': {'level': 'WARNING', 'handlers': ['console']},
                'handlers': {'console': {
                    'level': 'DEBUG', 'formatter': 'default',
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout'}}
            })
    logging.config.dictConfig(logging_config)

    logger.debug("Available logger:")
    for logger_name in logging.root.manager.loggerDict:
        logger.debug("   %s", logging.getLogger(logger_name))

    # Sensor data dictionary: Contains the most recent data of _all_ sensors,
    # including the timestamps (ts)
    all_sensor_data_ts = {}

    # Data logging, optionally into a CSV file
    ldb = None
    if config.csv is not None:
        logger.info("Opening CSV data log file '%s'", config.csv)
        log_labels = ["humidity", "radon_st", "radon_lt",
                      "temperature", "pressure", "co2", "voc"]
        try:
            with PerformanceCheck("LogDB/CSV file loading"):
                ldb = logdb.LogDB(
                        {config.name[sn]: log_labels for sn in config.sn},
                        config.csv,
                        number_retention_records=
                                int(config.data_retention/config.period))
            logger.info("  %d records read", ldb.get_nbr_active_records())
        except PermissionError:
            logger.error("  No permission to open file %s!", config.csv)
        except Exception as err:
            logger.critical("  Error accessing file %s : %s", config.csv, err)
            sys.exit(1)

    # Start the HTTP web server
    if config.port is not None:
        logger.info("Start HTTP/Web server on port %s", config.port)
        try:
            HandlerClass = ContextSpecificHttpRequestHandler(
                    all_sensor_data_ts, ldb, config["graph_decimations"])
            server = ThreadedHTTPServer(
                    ("", int(config.port)), HandlerClass)
            logger.info("  Done")
        except Exception:
            logger.critical("  Unable to open HTTP port %s!", config.port)
            logger.debug("    Stack trace:", exc_info=1)
            sys.exit(1)

    # Configure the mail alert
    actions = None
    if "alerts" in config:
        logger.info("Setup email alerts")
        if "smtp_server" not in config:
            logger.critical("  No SMTP server is configured!")
            sys.exit(1)
        try:
            actions = Actions(config.smtp_server, config.alerts)
            logger.info("  Done")

        except Exception as err:
            logger.critical("  Unable to setup the alerts: %s", err)
            logger.debug("    Stack trace:", exc_info=1)
            sys.exit(1)

    # Setup MQTT publishing
    mqtt_publisher = None
    if "mqtt" in config and "paho.mqtt.client" in sys.modules:
        logger.info("Setup MQTT publishing")
        try:
            mqtt_publisher = MqttPublisher(config.mqtt)
            logger.info("  Done")

        except Exception as err:
            logger.critical("  Unable to setup MQTT publishing: %s", err)
            logger.debug("    Stack trace:", exc_info=1)
            sys.exit(1)

    # Initialize the access to all Wave Plus devices
    logger.info("Setup WavePlus device access")
    wp_devices = []
    for sn in config.sn:
        if not config.emulation:
            wp_device = waveplus.WavePlus(sn, config.name[sn])
        else:
            wp_device = waveplus_emulation.WavePlus(sn, config.name[sn])
            logger.warning("Use WavePlus emulation module")
        wp_devices.append(wp_device)
    logger.info("  Done")

    # Main loop
    logger.info("Start main loop. Press ctrl+C to exit program!")
    iteration_start_time = time.time()
    if config.emulation:
        nbr_pre_emulated = config.data_retention/config.period
        if len(ldb.data["Time"]) < nbr_pre_emulated:
            iteration_start_time -= \
                    (nbr_pre_emulated-len(ldb.data["Time"]))*config.period
    while True:
        # Sensor data dictionaries: Contains the most recent data of the
        # available sensors that responded during the current iteration, with
        # and without the timestamps (ts, no_ts)
        sensor_data_no_ts = {}
        sensor_data_ts = {}

        try:
            for wp_device in wp_devices:
                logger.debug(
                        "Reading sensor data for device %s", wp_device.name)
                sdata_ts = sdata_no_ts = {}
                try:
                    # Read the senor values
                    sdata_no_ts = wp_device.get()
                    logger.debug("  -> %s", sdata_no_ts)
                    sdata_ts = sdata_no_ts.copy()
                    sdata_ts["update_time"] = int(time.time())
                except Exception as err:
                    logger.error("Failed to communicate with device %s: %s",
                                 wp_device.name, err)
                # Store the sensor values
                sensor_data_no_ts[wp_device.name] = sdata_no_ts
                sensor_data_ts[wp_device.name] = sdata_ts
                all_sensor_data_ts[wp_device.name] = sdata_ts

            # Store data in log database
            if ldb is not None:
                try:
                    ldb.insert(sensor_data_no_ts,
                               tstamp=int(iteration_start_time))
                except Exception as err:
                    logger.error("Failed to log the data: %s", err)
                    logger.debug("  Stack trace:", exc_info=1)

            # Check the sensor data level and trigger mail alerts
            if actions is not None:
                try:
                    actions.check_levels(sensor_data_no_ts)
                except Exception as err:
                    logger.error("Failed to trigger alerts: %s", err)
                    logger.debug("  Stack trace:", exc_info=1)

            # Publish eventual sensor data updates to a MQTT broker
            if mqtt_publisher is not None:
                try:
                    mqtt_publisher.publish(sensor_data_ts)
                except Exception as err:
                    logger.error("Failed to publish to MQTT broker: %s", err)
                    logger.debug("  Stack trace:", exc_info=1)

            # Wait until the next iteration has to start
            iteration_start_time += config.period
            if not config.emulation:
                time.sleep(max(0, iteration_start_time - time.time()))
            elif len(ldb.data["Time"]) > nbr_pre_emulated:
                time.sleep(max(0, iteration_start_time - time.time()))
        except (KeyboardInterrupt, SystemExit):
            logger.warning("Interrupt/termination request detected")
            break
        except Exception as err:
            logger.error("Error: *s", err)
            logger.debug("  Stack trace:", exc_info=1)
            pass

    # Close connections and files
    for wp_device in wp_devices:
        wp_device.stop()
    if mqtt_publisher is not None:
        mqtt_publisher.stop()
    if ldb is not None:
        ldb.close()

    logger.info("WavePlus_bridge ended")


if __name__ == "__main__":
    main()
