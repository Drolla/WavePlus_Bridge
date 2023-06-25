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

# pylint: disable=broad-except

import time
import struct
import logging
# pylint: disable-next=E0401
from bluepy.btle import UUID, Peripheral, Scanner, DefaultDelegate

logger = logging.getLogger(__name__)


class _Delegate(DefaultDelegate):
    """Bluetooth message receiver class
    
    The handleNotificaiton method will be called to receive notificaiton or
    indication messages.
    With the WavePlus device it has been observed that an indication message
    is not received in one chunk, but that the handleNotification method is
    called multiple times. For this reason that received messages are
    concatenuated.

    Args:
        mac: MAC address of the Airthing device
    """

    data = {}

    def __init__(self, mac):
        DefaultDelegate.__init__(self)
        self._mac = mac

        # Initialize the obtained message
        _Delegate.data[self._mac] = b""

    def handleNotification(self, handle, data):
        """Notificaiton handle that adds the message to the data buffer"""
        logger.debug("  Received notification (%s): %s", handle, data)
        _Delegate.data[self._mac] += data

    def get(self):
        """Get the recieved message"""
        return _Delegate.data[self._mac]


class _WavePlusSensors():
    """WavePlus sensor reading and parsing class
    
    Args:
        peripheral: BluePy peripheral class instance
    """

    _UUID = UUID("b42e2a68-ade7-11e4-89d3-123b93f75cba")
    _FORMAT = "<BBBBHHHHHHHH"
    _KEYS = ("humidity", "radon_st", "radon_lt", "temperature", "pressure",
             "co2", "voc")

    def __init__(self, peripheral):
        self._char = peripheral.getCharacteristics(uuid=self._UUID)[0]

    def get(self):
        """Read the sensor data and return it as dictionary"""
        raw_data = self._read_data()
        try:
            self._data_check(raw_data)
        except ValueError as error:
            logger.error(error)
            return {}
        value_array = struct.unpack(self._FORMAT, raw_data)
        sensor_data = self._decode(value_array)
        return sensor_data

    def _data_check(self, raw_data):
        """Check the received data and raise an error if it is not valid"""
        sensor_version = raw_data[0]
        if sensor_version != 1:
            raise ValueError(f"Unknown sensor version {sensor_version}")

    def _decode(self, value_array):
        """Parse the obtained data and format it in a dictionary"""
        return {
            "humidity": value_array[1]/2.0,
            "radon_st": self._conv2radon(value_array[4]),
            "radon_lt": self._conv2radon(value_array[5]),
            "temperature": value_array[6]/100.0,
            "pressure": value_array[7]/50.0,
            "co2": value_array[8]*1.0,
            "voc": value_array[9]*1.0
        }

    def _read_data(self):
        return self._char.read()

    @classmethod
    def get_keys(cls):
        """Get the keys provided by this class"""
        return cls._KEYS

    @staticmethod
    def _conv2radon(radon_raw):
        """ Validate or invalidate the radon value."""

        if 0 <= radon_raw <= 16383:
            return radon_raw
        return "N/A"


class _WavePlusControl():
    """WavePlus control data reading and parsing class
    
    Args:
        peripheral: BluePy peripheral class instance
    """

    _UUID = UUID("b42e2d06-ade7-11e4-89d3-123b93f75cba")
    _FORMAT='<BBL12B6H'
    _KEYS = ("illuminance", "battery") # Not implemented: measurement_periods
    _CMD=struct.pack('<B', 0x6d)
    _VBAT_MAX = 3.2
    _VBAT_MIN = 2.2

    def __init__(self, peripheral):
        self._periph = peripheral
        self._char = self._periph.getCharacteristics(uuid=self._UUID)[0]

    def get(self):
        """Read the control data and return it as dictionary"""

        raw_data = self._read_data()
        try:
            self._data_check(raw_data)
        except ValueError as error:
            logger.error(error)
            return {}
        value_array = struct.unpack(self._FORMAT, raw_data)
        control_data = self._decode(value_array)
        return control_data

    def _data_check(self, raw_data):
        """Check the received data and raise an error if it is not valid"""
        cmd = raw_data[0:1]
        if cmd != self._CMD:
            raise ValueError(f"Got data for wrong command: Expected \
                             {self._CMD.hex()}, got {cmd.hex()}")

        req_length = struct.calcsize(self._FORMAT)
        if len(raw_data) != req_length:
            raise ValueError(f"Wrong length data: Expected {req_length}), \
                              received {len(raw_data[2:])}")

    def _decode(self, value_array):
        """Parse the obtained data and format it in a dictionary"""
        illuminance = value_array[4]

        vbat = value_array[19] / 1000.0
        vbat_pct = 100 * round(max(1, min(0,
                vbat-self._VBAT_MIN)) / (self._VBAT_MAX - self._VBAT_MIN))

        control_data = {"illuminance": illuminance, "battery": vbat_pct}
        return control_data

    def _read_data(self):
        """Read the control data (battery level and illuminance data)"""

        # Define the notificaiton handle and turn notification on
        delegate = _Delegate(self._periph)
        self._periph.setDelegate(delegate)

        logger.debug("Control characteristics: Handle=%s/%s",
                     self._char.valHandle,
                     self._char.getHandle())
        logger.debug("  CCCD value (indication disabled): %s",
                     self._periph.readCharacteristic(self._char.valHandle+2))
        self._periph.writeCharacteristic(self._char.valHandle+2, b"\x02\x00")
        logger.debug("  CCCD value (indication enabled): %s",
                     self._periph.readCharacteristic(self._char.valHandle+2))

        # Send command to the characteristic
        self._periph.writeCharacteristic(self._char.valHandle, self._CMD)

        # Wait on notification, get the data, and disable notification
        logger.debug("Waiting on notificaiton")
        if not self._periph.waitForNotifications(10.0):
            logger.error("No notification received ...")
            return {}
        while self._periph.waitForNotifications(0.5):
            pass
        raw_data = delegate.get()
        logger.debug("Received data: %s", raw_data)
        self._periph.writeCharacteristic(self._char.valHandle+2, b"\x00\x00")

        return raw_data

    @classmethod
    def get_keys(cls):
        """Get the keys provided by this class"""
        return cls._KEYS


class WavePlus():
    """Airthings Wave Plus sensor reader class.

    This class provides all the functionalities to access a Wave Plus sensor
    and read its sensor values. The class instance is assigned to a specific
    sensor defined by its serial number:

        wp_device = waveplus.WavePlus(serial_number, my_sensor_name)

    The sensor data is provided by the get() method that handles
    also the connection to the device:

        wp_device.get()

    The returned sensor data is returned in form of a dictionary.

    Args:
        serial_number: Serial number of the device
        [name]: Optional nick name of the device
    """

    # Serial number & device address cache that allows avoiding new scan phases
    # if multiple WavePlus devices are used (class variable)
    _sn2addr = {}

    def __init__(self, serial_number, name=""):
        # The constructor does nothing else than registering the serial number
        # and the nick name. If no nickname is provided, it is defaulted to the
        # serial number.
        self._periph = None
        self._sensor = None
        self._control = None
        self._mac = None
        self._sn = str(serial_number)
        self._name = name if name != "" else str(serial_number)

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

    def discover(self):
        """Discover the device defined via the serial number
        
        This method launches the BLE scanner 50 times to find the specified
        device. All discovered devices are cached. If a device that has to
        be sicovered is already cached, no scanning is performed."""
        # Device is known, there is nothing to discover
        if self._mac is not None:
            return

        # Check if device is already known (from scanning another device)
        if self._sn in WavePlus._sn2addr:
            logger.info("  Device %s previously found, MAC address=%s",
                        self._sn, self._mac)
            self._mac = WavePlus._sn2addr[self._sn]
            return

        # Scan for the device
        logger.debug("Initialize scanning/discovery")
        scanner = Scanner().withDelegate(DefaultDelegate())
        search_count = 0
        while search_count < 50:
            logger.debug("  Run scan")
            devices = scanner.scan(0.1)  # 0.1 seconds scan period
            search_count += 1
            for dev in devices:
                manu_data = dev.getValueText(255)
                print("  Manufacturing data:", manu_data)
                sn = self._parse_serial_number(manu_data)
                logger.debug("  Found device %s", sn)

                # A serial number has been found. Register it
                if sn is not None and sn not in WavePlus._sn2addr:
                    WavePlus._sn2addr[sn] = dev.addr

                # The device with the defined serial number has been found
                if sn == self._sn:
                    logger.info("  Device %s found, MAC address=%s",
                                self._sn, self._mac)
                    self._mac = dev.addr
                    return

    def connect(self):
        """Establish a BLE connection to the device

        The BLE connection happens via the MAC address of the device. If the
        address is not known, the device is scanned. The addresses of each
        detected device is cached to limit the number of required device
        scanning.
        """

        logger.debug("Connect to %s", self._sn)

        # Ensure that the device (MAC) is known. Scan for the device otherwise
        self.discover()
        if self._mac is None:
            raise ConnectionError("Could not find device " + self._sn)

        # Connect to device
        if self._periph is None:
            self._periph = Peripheral(self._mac)
        if self._sensor is None:
            self._sensor = _WavePlusSensors(self._periph)
        if self._control is None:
            self._control = _WavePlusControl(self._periph)

    def disconnect(self):
        """Disconnect the connected device"""
        if self._periph is not None:
            try:
                self._periph.disconnect()
            except Exception:
                pass
            self._periph = None
            self._sensor = None
            self._control = None

    def get(self, retries=3, retry_delay=1.0):
        """Return the sensor data as well as the battery level and illuminance

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
                sensor_data = self._sensor.get()
                control_data = self._control.get()
                self.disconnect()
                logger.debug("  -> %s", sensor_data)
                return dict(**sensor_data, **control_data)
            except Exception as error:
                logger.warning("Failed to communicate with device \
                               %s (attempt %s of %s): %s",
                               self._name, attempt, retries + 1, error)
                logger.debug("  Stack trace:", exc_info=1)
            if attempt < retries:
                logger.debug("Retrying in %s seconds", retry_delay)
                time.sleep(retry_delay)

        raise ConnectionError("Failed to communicate with device {}/{}".format(
                self._sn, self._name))

    @classmethod
    def get_keys(cls):
        return _WavePlusSensors.get_keys() + _WavePlusControl.get_keys()

    @staticmethod
    def _parse_serial_number(hex_string):
        """Parse the manufacturing data and returns the serial number
        
        Returns None if the provided data is invalid
        """
        if hex_string is None:
            return None
        try:
            manu_data = struct.unpack("<HLBB", bytearray.fromhex(hex_string))
        except struct.error:
            return None
        if manu_data[0] != 0x0334:
            return None
        return str(manu_data[1])

    @property
    def name(self):
        return self._name


#############################################
# Main
#############################################

if __name__ == "__main__":
    import sys

    def help_and_exit():
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
        help_and_exit()
    period = int(sys.argv[1])
    serial_numbers = []
    for serial_number in sys.argv[2:]:
        if serial_number.isdigit() is not True or len(serial_number) != 10:
            help_and_exit()
        serial_numbers.append(serial_number)

    # Setup the devices
    wp_devices = []
    for serial_number in serial_numbers:
        logger.info("Setup device %s", serial_number)
        wp_devices.append(WavePlus(serial_number))

    logger.info("Entering into sensor read loop. Exit with Ctrl+C")

    # Print the table header that includes all sensor names
    keys = WavePlus.get_keys()
    log_separator = "+" + ((("-" * 12) + "+") * (len(keys)+1))
    log_format = log_separator + "\n|" + \
                 ("{:>12}|" * (len(keys)+1)) + "\n" + log_separator
    logger.info(log_format.format("Device", *keys))

    # Infinite loop where all sensors are repeatably read
    while True:
        for wp_device in wp_devices:
            try:
                wp_device_data = wp_device.get()
                wp_device_values = ["" if key not in wp_device_data else wp_device_data[key] for key in keys]
                logger.info(log_format.format(wp_device.name, *wp_device_values))
            except KeyboardInterrupt:
                break
            except Exception as err:
                logger.error("Failed to communicate with device %s: %s",
                             wp_device.name, err)
                logger.exception("  Stack trace:")
        time.sleep(period)

    del wp_devices
    logger.warning("waveplus ended")
