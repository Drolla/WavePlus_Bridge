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


class WavePlus():
    """Airthings Wave Plus sensor reader class.

    This class provides all the functionalities to access a Wave Plus sensor
    and read its sensor values. The class instance is assigned to a specific
    sensor defined by its serial number (sn):

        wp_device = waveplus.WavePlus(serial_number, my_sensor_name)

    The sensor data are provided by the get() method that handles also the
    connection to the device:

        wp_device.get()

    The returned sensor data is returned in form of a dictionary.

    Args:
        sn: Serial number of the device
        [name]: Optional nick name of the device
    """

    # Serial number & device address cache that allows avoiding new scan phases
    # if multiple WavePlus devices are used (class variable)
    sn2addr = {}

    def __init__(self, sn, name=""):
        # The constructor does nothing else than registering the serial number
        # and the nick name. If no nickname is provided, it is defaulted to the
        # serial number.
        self.periph = None
        self.val_char = None
        self.mac_addr = None
        self.sn = str(sn)
        self.name = name if name != "" else str(sn)
        self.uuid = UUID("b42e2a68-ade7-11e4-89d3-123b93f75cba")

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

        logger.debug("Connect to %s", self.sn)

        # Check if device is already known (from scanning another device)
        if self.mac_addr is None and self.sn in WavePlus.sn2addr:
            self.mac_addr = WavePlus.sn2addr[self.sn]
            logger.info("  Device %s previously found, MAC address=%s",
                        self.sn, self.mac_addr)

        # Auto-discover device on first connection
        if self.mac_addr is None:
            logger.debug("  MAC address unknown, initialize scanning")
            scanner = Scanner().withDelegate(DefaultDelegate())
            searchCount = 0
            while self.mac_addr is None and searchCount < 50:
                logger.debug("    Run scan")
                devices = scanner.scan(0.1)  # 0.1 seconds scan period
                searchCount += 1
                for dev in devices:
                    ManuData = dev.getValueText(255)
                    sn = self.parse_serial_number(ManuData)
                    logger.debug("      Found device %s", sn)
                    if sn is not None and sn not in WavePlus.sn2addr:
                        WavePlus.sn2addr[sn] = dev.addr

                    # Serial number has been found. Register the other devices
                    if sn == self.sn:
                        self.mac_addr = dev.addr

            if self.mac_addr is None:
                raise ConnectionError("Could not find device " + self.sn)

            logger.info("  Device %s found, MAC address=%s",
                        self.sn, self.mac_addr)

        # Connect to device
        if self.periph is None:
            self.periph = Peripheral(self.mac_addr)
        if self.val_char is None:
            self.val_char = self.periph.getCharacteristics(uuid=self.uuid)[0]

    def read(self):
        """Read the raw sensor data"""

        if (self.val_char is None):
            logger.error("Device is not connected: %s", self.sn)
            raise ConnectionError("Device is not connected" + self.sn)
        rawdata = self.val_char.read()
        rawdata = struct.unpack("BBBBHHHHHHHH", rawdata)
        sensors = Sensors()
        sensors.set(rawdata)
        return sensors

    def disconnect(self):
        if self.periph is not None:
            try:
                self.periph.disconnect()
            except Exception:
                pass
            self.periph = None
            self.val_char = None

    def get(self, retries=3, retry_delay=1.0):
        """Return the sensor data

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

        logger.debug("Reading sensor data for device %s", self.name)

        for attempt in range(retries + 1):
            try:
                self.connect()
                sensor_data = self.read().get()
                self.disconnect()
                logger.debug("  -> %s", sensor_data)
                return sensor_data
            except Exception as err:
                logger.error("Failed to communicate with 'device' "
                             "%s (attempt %s of %s): %s",
                             self.name, attempt, retries + 1, err)
                # logger.exception("  Stack trace:")
            if attempt < retries:
                logger.debug("Retrying in %s seconds", retry_delay)
                time.sleep(retry_delay)

        raise Exception("Failed to communicate with device {}/{}".format(
                self.sn, self.name))

    @staticmethod
    def parse_serial_number(RawHexStr):
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


class Sensors():
    def __init__(self):
        self.sensor_version = None
        self.init_sensor_data()

    def init_sensor_data(self):
        self.sensor_data = {}
        for key in ("humidity", "radon_st", "radon_lt",
                    "temperature", "pressure", "co2", "voc"):
            self.sensor_data[key] = None

    def set(self, rawData):
        self.sensor_version = rawData[0]
        if (self.sensor_version != 1):
            logger.error("Unknown sensor version (%s)", self.sensor_version)
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
        return "N/A"

    def get(self):
        return self.sensor_data


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
    sensor_keys = Sensors().sensor_data.keys()
    log_separator = "+" + ((("-" * 12) + "+") * (len(sensor_keys)+1))
    log_format = log_separator + "\n|" + \
                 ("{:>12}|" * (len(sensor_keys)+1)) + "\n" + log_separator
    logger.info(log_format.format("Device", *sensor_keys))

    # Infinite loop where all sensors are repeatably read
    while True:
        for wp_device in wp_devices:
            try:
                sensor_values = wp_device.get().values()
                logger.info(log_format.format(wp_device.name, *sensor_values))
            except KeyboardInterrupt:
                break
            except Exception as err:
                logger.error("Failed to communicate with device %s: %s",
                             wp_device.name, err)
                logger.exception("  Stack trace:")
        time.sleep(period)

    del wp_device
    logger.warning("waveplus ended")
