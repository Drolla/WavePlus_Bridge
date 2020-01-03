# Airthings **Wave Plus Bridge** to Wifi/LAN

This tool provides a bridge between one or multiple Airthings Wave Plus sensors and the Wifi/LAN network, using a Raspberry Pi that supports Bluetooth Low Energy (BLE) (e.g. Raspberry PI nano W). In detail, the bridge provides the following features:
 
* Wave Plus sensor monitoring
  - Scanning of one or multiple Wave Plus devices in a user definable interval
* HTTP web server
  - Presentation of the Wave Plus sensor data as HTML web page
  - Exposure of the sensor data via a JSON API
* CSV logging of the sensor data

The tool runs with Python 3.x. It can be installed as a service that is launched automatically when the Raspberry Pi boots.


# Requirements

## Hardware requirements

* One or multiple Airthings Wave Plus devices
* A Raspberry PI that supports Bluetooth Low Energy (BLE) (by providing either built-in support or via a Bluetooth adapter)

The tool has been tested on a Rasperry Pi nano W that runs with Raspbian Buster. Two Wave Plus devices have been accessed.

It should be ensured that the Wave Plus devices run the latest firmware. To do so, they should have been connected once to the official Airthings IPhone/Android application.

## Software requirements

* Python 3
* The Python 3 library BluePy
* The Python 3 library argparse
* The Python 3 library yaml
* The Python 3 library json

The tool has been tested with Python 3.x and BluePy 1.x.x for Python 3.
To install the required packages, additional ones may need to be installed (e.g. PIP3).

# Setup

## Wave Plus Bridge Setup

TBD

## Raspberry Pi Setup

TBD
