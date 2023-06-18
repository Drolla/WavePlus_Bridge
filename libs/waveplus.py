"""Airthings Wave Plus sensor reader

The two classes, WavePlus and Sensors, has been provided by Airthings under the
MIT licenses. The code has been slightly modified. The original code is
available here:
                https://github.com/Airthings/waveplus-reader

Copyright (C) 2020-2022 Andreas Drollinger
Portions Copyright (C) 2018 Airthings
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import time
import struct
import logging
from bluepy.btle import UUID, Peripheral, Scanner, DefaultDelegate

logger = logging.getLogger(__name__)

_UUID_DATA = UUID("b42e2a68-ade7-11e4-89d3-123b93f75cba")
_UUID_CONTROL = UUID("b42e2d06-ade7-11e4-89d3-123b93f75cba")


class WavePlus():
    """Airthings Wave Plus sensor reader class.

    This class provides all the functionalities to access a Wave Plus sensor
    and read its sensor values. The class instance is assigned to a specific
    sensor defined by its serial number (sn):

        wp_device = waveplus.WavePlus(serial_number, my_sensor_name)

    The sensor data is provided by the get() method that handles
    also the connection to the device:

        wp_device.get()

    The returned sensor data is returned in form of a dictionary.

    Args:
        sn: Serial number of the device
        [name]: Optional nick name of the device
    """

    # Serial number & device address cache that allows avoiding new scan phases
    # if multiple WavePlus devices are used (class variable)
    _sn2addr = {}

    def __init__(self, sn, name=""):
        # The constructor does nothing else than registering the serial number
        # and the nick name. If no nickname is provided, it is defaulted to the
        # serial number.
        self._periph = None
        self._data_char = None
        self._control_char = None
        self._mac = None
        self._sn = str(sn)
        self._name = name if name != "" else str(sn)

    def stop(self):
        """Stops the BLE connection to the device

        Call preferably this function to stop the connection instead of
        deleting the object instance to ensure a controlled disconnection.
        """
        try:
            self.disconnect()
        except Exception:
            pass

    def __del__(self):
        self.stop()

    def connect(self):
        """Establish a BLE connection to the device

        The BLE connection happens via the MAC address of the device. If the
        address is not known, the device is scanned. The addresses of each
        detected device is cached to limit the number of required device
        scanning.
        """

        logger.debug("Connect to %s", self._sn)

        # Check if device is already known (from scanning another device)
        if self._mac is None and self._sn in WavePlus._sn2addr:
            self._mac = WavePlus._sn2addr[self._sn]
            logger.info("  Device %s previously found, MAC address=%s",
                        self._sn, self._mac)

        # Auto-discover device on first connection
        if self._mac is None:
            logger.debug("  MAC address unknown, initialize scanning")
            scanner = Scanner().withDelegate(DefaultDelegate())
            searchCount = 0
            while self._mac is None and searchCount < 50:
                logger.debug("    Run scan")
                devices = scanner.scan(0.1)  # 0.1 seconds scan period
                searchCount += 1
                for dev in devices:
                    ManuData = dev.getValueText(255)
                    sn = self._parse_serial_number(ManuData)
                    logger.debug("      Found device %s", sn)
                    if sn is not None and sn not in WavePlus._sn2addr:
                        WavePlus._sn2addr[sn] = dev.addr

                    # Serial number has been found. Register the other devices
                    if sn == self._sn:
                        self._mac = dev.addr

            if self._mac is None:
                raise ConnectionError("Could not find device " + self._sn)

            logger.info("  Device %s found, MAC address=%s",
                        self._sn, self._mac)

        # Connect to device
        if self._periph is None:
            self._periph = Peripheral(self._mac)
        if self._data_char is None:
            self._data_char = self._periph.getCharacteristics(uuid=_UUID_DATA)[0]
        if self._control_char is None:
            self._control_char = self._periph.getCharacteristics(uuid=_UUID_CONTROL)[0]

    def read_sensor_data(self):
        """Read the raw sensor data"""

        if (self._data_char is None):
            logger.error("Device is not connected: %s", self._sn)
            raise ConnectionError("Device is not connected" + self._sn)
        raw_data = self._data_char.read()
        value_array = struct.unpack("BBBBHHHHHHHH", raw_data)

        sensor_version = value_array[0]
        if (sensor_version != 1):
            logger.error("Unknown sensor version (%s)", sensor_version)
        sensor_data = {
            "humidity": value_array[1]/2.0,
            "radon_st": self._conv2radon(value_array[4]),
            "radon_lt": self._conv2radon(value_array[5]),
            "temperature": value_array[6]/100.0,
            "pressure": value_array[7]/50.0,
            "co2": value_array[8]*1.0,
            "voc": value_array[9]*1.0
        }
        return sensor_data

    def read_control_data(self):
        """Read the control data (battery level and luminity)"""

        FORMAT_TYPE='<L12B6H'
        CMD=struct.pack('<B', 0x6d)

        if (self._control_char is None):
            logger.error("Device is not connected: %s", self._sn)
            raise ConnectionError("Device is not connected" + self._sn)
        raw_data = self._control_char.read()
        cmd = raw_data[0:1]
        if cmd != CMD:
            logger.warning("Got data for wrong command: Expected %s, got %s",
                           CMD.hex(), cmd.hex())
            return {}
        
        if len(raw_data[2:]) != struct.calcsize(self.format_type):
            logger.debug("Wrong length data received (%d), expected (%d)",
                         len(cmd), struct.calcsize(self.format_type))
            return {}
        value_array = struct.unpack(FORMAT_TYPE, raw_data[2:])
        control_data = {
            "luminance": value_array[2],
            "battery": value_array[17] / 1000.0,
            # "measurement_periods": "value_array[5],
        }
        return control_data

    def disconnect(self):
        if self._periph is not None:
            try:
                self._periph.disconnect()
            except Exception:
                pass
            self._periph = None
            self._data_char = None
            self._control_char = None

    def get(self, retries=3, retry_delay=1.0):
        """Return the sensor data as well as the battery level and luminity

        This method connects to the device, reads the raw sensor data and
        translates it into a sensor data dictionary, and disconnect from the
        device again. If this sequence fails, additional retries can be
        optionally performed.

        Args:
            [retries]: Number of extra attempts to read from the device.
                       Default=3.
            [retry_delay]: Amount of time in seconds to wait before attempting
                           reconnection.
        """

        logger.debug("Reading sensor data for device %s", self._name)

        for attempt in range(1, retries + 2):
            try:
                self.connect()
                sensor_data = self.read_sensor_data()
                control_data = self.read_control_data()
                self.disconnect()
                logger.debug("  -> %s", sensor_data)
                return sensor_data | control_data
            except Exception as err:
                logger.warning("Failed to communicate with device "
                               "%s (attempt %s of %s): %s",
                               self._name, attempt, retries + 1, err)
                logger.debug("  Stack trace:", exc_info=1)
            if attempt < retries:
                logger.debug("Retrying in %s seconds", retry_delay)
                time.sleep(retry_delay)

        raise Exception("Failed to communicate with device {}/{}".format(
                self._sn, self._name))

    @staticmethod
    def get_sensor_keys():
        return ("humidity", "radon_st", "radon_lt", "temperature", "pressure",
                "co2", "voc")

    @staticmethod
    def get_control_keys():
        return ("luminance", "battery") # "measurement_periods"

    @staticmethod
    def get_keys():
        return WavePlus.get_sensor_keys() + WavePlus.get_control_keys()

    @staticmethod
    def _parse_serial_number(RawHexStr):
        if RawHexStr is None:
            sn = None
        else:
            ManuData = bytearray.fromhex(RawHexStr)
            if (((ManuData[1] << 8) | ManuData[0]) == 0x0334):
                sn = ManuData[2] | (ManuData[3] << 8) \
                   | (ManuData[4] << 16) | (ManuData[5] << 24)
                sn = str(sn)
            else:
                sn = None
        return sn

    @staticmethod
    def _conv2radon(radon_raw):
        """ Validate or invalidate the radon value."""
        if 0 <= radon_raw <= 16383:
            return radon_raw
        return "N/A"


#############################################
# Main
#############################################

if __name__ == "__main__":
    import sys

    def help():
        print("Usage: waveplus.py <period> "
              "<serial_number_1> [serial_number_2] ..")
        sys.exit(1)

    # Configure the logger
    logger.setLevel(logging.DEBUG)
    log_handler = logging.StreamHandler()
    log_handler.setLevel(logging.DEBUG)
    logger.addHandler(log_handler)

    # Handle the arguments (1: sensor read period, 2..: serial numbers)
    if len(sys.argv) < 3 or \
            sys.argv[1].isdigit() is not True or int(sys.argv[1]) < 0:
        help()
    period = int(sys.argv[1])
    serial_numbers = []
    for serial_number in sys.argv[2:]:
        if serial_number.isdigit() is not True or len(serial_number) != 10:
            help()
        serial_numbers.append(serial_number)

    # Setup the devices
    wp_devices = []
    for serial_number in serial_numbers:
        logger.info("Setup device %s", serial_number)
        wp_devices.append(WavePlus(serial_number))

    logger.info("Entering into sensor read loop. Exit with Ctrl+C")

    # Print the table header that includes all sensor names
    keys = WavePlus(None).get_keys()
    log_separator = "+" + ((("-" * 12) + "+") * (len(keys)+1))
    log_format = log_separator + "\n|" + \
                 ("{:>12}|" * (len(keys)+1)) + "\n" + log_separator
    logger.info(log_format.format("Device", *keys))

    # Infinite loop where all sensors are repeatably read
    while True:
        for wp_device in wp_devices:
            try:
                wp_device_data = wp_device.get()
                logger.info(log_format.format(wp_device._name, *wp_device_data))
            except KeyboardInterrupt:
                break
            except Exception as err:
                logger.error("Failed to communicate with device %s: %s",
                             wp_device._name, err)
                logger.exception("  Stack trace:")
        time.sleep(period)

    del wp_device
    logger.warning("waveplus ended")
