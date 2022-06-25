"""Airthings Wave Plus sensor reader emulation

The WavePlus class implemented in this file emulates the class of the same name
provided in ../libs and used by the Wave Plus Bridge application. It is used
for testing purposes and operates without Bluetooth LE (BLE) library and
without connection of a real Wave Plus device. It is loaded if the Wave Plus
Bridge is executed in this ./test folder, and if either the flag '--emulation'
is provided to the application or the parameter 'emulation' is set to 'True' in
the provided YAML configuration file.

Copyright (C) 2020-2022 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import random
import logging

logger = logging.getLogger(__name__)

#############################################
# Emulated sensor
#############################################

class EmulatedSensor:
    def __init__(self, min, max):
        self.min = min
        self.max = max
        self.value = (min+max)/2

    def get(self):
        self.value = round(
                self.value +
                random.random() * (self.max-self.value)/20 -
                random.random() * (self.value-self.min)/20, 1)
        if self.value > self.max:
            self.value = self.max
        if self.value < self.min:
            self.value = self.min
        return self.value


#############################################
# WavePlus test classes
#############################################

class WavePlus():
    def __init__(self, sn, name=""):
        self.sn = sn
        self.name = name if name != "" else sn

    def get(self):
        logger.debug("Reading sensor data for device %s", self.name)
        return {
            "humidity": EmulatedSensor(20, 100).get(),
            "radon_st": EmulatedSensor(20, 500).get(),
            "radon_lt": EmulatedSensor(20, 500).get(),
            "temperature": EmulatedSensor(10, 35).get(),
            "pressure": EmulatedSensor(20, 500).get(),
            "co2": EmulatedSensor(20, 500).get(),
            "voc": EmulatedSensor(20, 1000).get()
        }


if __name__ == "__main__":
    wp = WavePlus(12345, "test_device")
    print("Read 3 data records:")
    print("  ", wp.get())
    print("  ", wp.get())
    print("  ", wp.get())
    print("Done")
