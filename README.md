# Airthings **Wave Plus Bridge** to Wifi/LAN and MQTT

This tool provides a bridge between one or multiple **Airthings Wave Plus** sensors and the **Wifi/LAN** network, using a **Raspberry Pi** that supports Bluetooth Low Energy (BLE). In detail, the bridge provides the following features:
 
* Wave Plus sensor monitoring
  - Scanning of one or multiple Wave Plus devices in a user definable interval
* HTTP web server
  - Presentation of the Wave Plus sensor data as HTML web page
  - Exposure of the sensor data via a JSON API
* Email alerts
  - High flexibility in specifying alert conditions
* MQTT publishing
  - Optional publishing of the sensor data to an MQTT broker
* Logging of the sensor data in a CSV file

The tool runs with Python 3.x. It can be installed as a service that is launched automatically when the Raspberry Pi boots.

![Concept picture](Concept.png)

## Table of contents

* [Requirements](#requirements)
    * [Hardware Requirements](#hardware-requirements)
    * [Software Requirements](#software-requirements)
* [Wave Plus Bridge Configuration](#wave-plus-bridge-configuration)
    * [Command Line Configuration](#command-line-configuration)
    * [YAML based Configuration](#yaml-based-configuration)
* [Wave Plus Bridge Installation](#wave-plus-bridge-installation)
    * [Wave Plus Bridge Installation](#wave-plus-bridge-installation)
    * [Setup the Wave Plus Bridge as a Service](#setup-the-wave-plus-bridge-as-a-service)
* [Raspberry Pi Installation](#raspberry-pi-installation)
    * [Raspbian installation](#raspbian-installation)
    * [Python Library Installation (Bullseye and before)](#python-library-installation-bullseye-and-before)
    * [Python Library Installation (Bookworm and later)](#python-library-installation-bookworm-and-later)
* [Debugging](#debugging)
    * [Some simple checks](#some-simple-checks)
    * [Run the Wave Plus communication test application](#run-the-wave-plus-communication-test-application)
    * [Run the Wave Plus Bridge using a minimalist configuration](#run-the-wave-plus-bridge-using-a-minimalist-configuration)
    * [Email and SMTP server configuration](#email-and-smtp-server-configuration)
    * [MQTT configuration](#mqtt-configuration)
    * [Enable logging of additional debug information](#enable-logging-of-additional-debug-information)
* [Related topics](#related-topics)

# Requirements

## Hardware Requirements

The following hardware components are required to run the Wave Plus Bridge:

* One or multiple Airthings Wave Plus devices
* A Raspberry PI that supports Bluetooth Low Energy (BLE) (by providing either built-in support or via a Bluetooth adapter)

It should be ensured that the Wave Plus devices run the latest firmware. To do so, they should have been connected once to the official Airthings iPhone/Android application.

The tool has been tested on a Raspberry Pi Zero W and on a Raspberry Pi 4, both running on Raspbian Buster. Two Wave Plus devices have been simultaneously accessed.


## Software Requirements

The following software packages need to be installed on the Raspberry Pi:

* Python 3
* The Python 3 library BluePy
* The Python 3 library yaml (PyYAML)
* The Python 3 library paho-mqtt (if MQTT publishing is required)

The tool has been tested with Python 3.7.2, BluePy 1.3.0 and paho-mqtt 1.5.1.

The sections [Raspbian installation](#raspbian-installation) and [Python Library Installation](#python-library-installation) provide support for the installation of the Raspbian OS and the Python library installation.


# Wave Plus Bridge Configuration

The Wave Plus Bridge can be configured via command line arguments, via a YAML configuration file or via a combination of both of them. The command line arguments have precedence over the YAML configuration file, which has been used in an example below to override the log file definition. Advanced configurations, e.g. email alerts, can only be performed via the YAML file and not via command line arguments.


## Command Line Configuration

Running the Wave Plus Bridge Python program with the *-h* argument will provide comprehensive instructions about the tool configurations:

```
sudo /opt/waveplus_bridge/waveplus_bridge.py -h
```

```
usage: waveplus_bridge.py [-h] [--period PERIOD]
                          [--data_retention DATA_RETENTION] [--port PORT]
                          [--csv CSV] [--log LOG] [--config CONFIG]
                          [--report_performance] [sn [sn ...]]

Wave Plus to Wifi/LAN Bridge

Positional arguments:
  sn                    10-digit serial number of a Wave Plus device (see
                        under the magnetic backplate. This number can be
                        combined with a device nickname, separated by a column
                        from the serial number ("2931234567, my_office")

Optional arguments:
  -h, --help            Show this help message and exit
  --period PERIOD       Time in seconds between reading the sensor values
  --data_retention DATA_RETENTION
                        Data retention time in seconds
  --port PORT           Port of the HTTP web server
  --csv CSV             CSV file to store data
  --log LOG             Log file. If not specified the stdout is used
  --config CONFIG       YAML configuration file
```


## YAML based Configuration

The same and additional parameters can also be configured via YAML files specified with the --config command line argument. The Wave Plus Bridge package provides a YAML template file (waveplus_bridge.yaml) that has to be adapted to the specific needs.


### Basic Configuration

The basic configuration includes the specification of the Wave Plus devices serial numbers, the sensor update period, the HTTP port and optionally the log file.

```
# Update period: Time in seconds between reading the sensor values
period: 120

# Number of extra attempts to read from the device after a connection failure
retries: 3

# Amount of time in seconds to wait before attempting reconnection
retry_delay: 1

# SN: List of 10-digit serial number of one or multiple Wave Plus devices (see 
# under the magnetic backplate. Each number can be combined with a device 
# nickname, separated by a column from the serial number 
# (e.g. "2931234567, my_office").
sn:
   - 2931234567, my_office
   - 2931234569, my_living

# HTTP/Web server port: If no HTTP/web server is required, comment the 
# following line.
port: 80

# Log file: Comment the following line to log all information to stdout.
# For more sophisticated logging configurations, for example for debugging, see
# section 'Debugging' of README.md.
log: /var/log/waveplus_bridge.log
```

### CSV Database and Graph Generation

The CSV database is used to generate data graphs on the HTML page and to allow processing the data in external tools. The CSV file is reloaded after a restart, which guarantees that the generated graphs shows also the previously recorded data.

```
# CSV log file: If no CSV data logging is required, comment the following line.
csv: /var/log/waveplus_bridge.csv

# Data retention time in seconds (to limit the memory use)
data_retention: 2678400 # 31 days

# The graph decimation allows reducing the CSV data used to generate the graphs 
# (see logdb.get_csv)
graph_decimations:
   -1.0: 8  # -31 days (full range)
   -5760: 3 # - 8 days
   -750: 1  # - 25 hours
```

### EMail Alerts

Email alerts can be sent when certain conditions are met (e.g. radon level higher than 100 Bq/m3 for more than 1 hour). To send such email alerts, an SMTP server has to be specified and one or multiple alert triggers defined.

The following lines show an example of a SMTP server configuration:

```
smtp_server:
    # Mail server address
    server: mail.server.com

    # Mail server port, e.g. 25, 465, 587
    port: 465
    
    # Options: SSL, TLS, or no definition (default)
    security: SSL
    
    # Login user name
    user: wave@plus.com
    
    # Login user password
    password: bridge123
```

One or multiple alerts can be defined. Each alert has one or multiple sources (device sensors), a trigger and one or multiple actions.

The first example of an email alert configuration uses the simplest form (single source, single threshold level, single mail destination address). Comprehensive explanations about the parameters are given in the 2nd example. The alert configuration is added in form of a list (starting with "-") to allow adding additional configurations:

```
alerts:
    -   sources:
            my_office:radon_st
        trigger:
            above: 150
            for: "00:30:00"
            min_interval: "01:00:00"
        actions:
            mail:
                from: wave.plus@myhome.com
                to: sophia.millar@family.com
```

The second alert configuration uses multiple sources, trigger levels and mail destination addresses. It provides all necessary information to understand the configuration options:

```
# Remove the following line (alerts:) if this example should be concatenated to
# the previous one.
alerts:
    -   # At least one source (device:sensors) has to be defined as trigger
        # source. The example shows the definition of multiple sources 
        # (list form):
        sources:
            - my_office:radon_st
            - my_living:radon_st

        # Various parameters allow defining the exact conditions when 
        # triggering should occur:
        trigger:
            # A triggering happens if a sensor value is above or below a 
            # certain level. In this sense, the condition can be specified 
            # with the keywords 'above' or 'bellow' and a single threshold
            # level, or as the example shows, as a list of threshold levels.
            above: [100, 200, 400, 1000]

            # 'For' delays the trigger until the specified condition is valid
            # for a time span specified either in seconds, or in the format
            # Hours:Minutes:Seconds. The trigger delay is applied individually
            # for each specified trigger threshold level:
            for: "00:30:00"

            # 'min_interval' allows specifying a minimum re-triggering 
            # interval. The provided value is specified either in seconds, or 
            # in the format Hours:Minutes:Seconds. The minimum re-triggering
            # interval is not respected if the re-triggering is due to a
            # higher trigger threshold level than the previously triggering.
            min_interval: "01:00:00"

        # One or multiple actions can be specified. An action can be a mail 
        # alert, or a message to the stdout and to the log file.
        # Both mail and print alerts allow customizing the alert information 
        # with the keyword 'message'. The specified message may contain the
        # following placeholders: %v: sensor value, %d: device, %s: device 
        # sensor.
        # The example below shows the definition of a mail alert and a print 
        # alert (list starting with "-"):
        actions:
            -   mail:
                    # Author mail address
                    from: wave.plus@myhome.com

                    # Single or multiple destination addresses. Multiple 
                    # addresses as shown in the example are provided in form 
                    # of a list
                    to:
                        - liam.smith@family.com
                        - olivia.brown@family.com

                    # Mail subject
                    subject: 'Radon alert'

                    # Mail message, see above
                    message: |-
                        Radon level is too high!
                        Sensor: %d, %s
                        Level: %v'
            -   print:
                    # Print message, see above
                    message: |-
                        Radon level is too high!
                        Sensor: %d, %s
                        Level: %v'
```

In case mails are not successfully sent, consult section [Email/SMTP server configuration](#email/smtp-server-configuration).

### MQTT publishing

The sensor data can be published to an MQTT server. To do so, the MQTT broker, the parameters to setup the connection to it, as well as the devices and sensors that should be exposed, have to be specified in the following way:

```
mqtt:
    # MQTT broker host IP address
    host: test.mosquitto.org

    # MQTT broker port
    port: 1883

    # Optional client ID
    # client_id: clientId-clxHpr9
    
    # Optional authentication data composed by a user name and a password
    # auth:
    #     username: <username>
    #     password: <password>
    
    # Optional TLS configuration parameters. If present, ca_certs is required, 
    # all other all other parameters are optional, which results in the client 
    # using the default behavior.
    # tls:
    #     ca_certs: <ca_certs>
    #     certfile: <certfile>
    #     keyfile: <keyfile>
    #     tls_version: <tls_version>
    #     ciphers: <ciphers>
    
    # MQTT topic root: The topics for the different parameters to publish will 
    # be composed in the following way: <topic root>/<device>/<sensor>
    topic: my_nice_home/waveplus_bridge

    # List the Wave Plus devices and their sensors that should be published. A
    # list of sensors to publish can be assigned to each device:
    #    <devicename>: ['<sensor1>', '<sensor2'>, ...]
    # The wildcard character '*' (enclosed in '') can be used to select all 
    # sensors:
    #    <devicename>: '*'
    publish:
        my_office: [radon_st, radon_lt]
        my_living: '*'
```


# Wave Plus Bridge Installation


## Wave Plus Bridge Installation

The following commands install the Wave Plus Bridge in the directory /opt/waveplus_bridge.

Download and unzip the Wave Plus Bridge software from GitHub:

```
wget https://github.com/Drolla/WavePlus_Bridge/archive/master.zip
unzip master.zip
```

Copy it to /opt/waveplus_bridge, and make the Main Python script executable:

```
sudo mv WavePlus_Bridge-master /opt/waveplus_bridge
sudo chmod 775 /opt/waveplus_bridge/waveplus_bridge.py
```

Adapt the configuration, see [Wave Plus Bridge Configuration](#wave-plus-bridge-configuration):

```
sudo nano /opt/waveplus_bridge/waveplus_bridge.yaml
```

The Wave Plus Bridge is now ready to be started. To get the log information displayed directly on the terminal for debugging purposes, override the log file definition (--log argument):

```
sudo /opt/waveplus_bridge/waveplus_bridge.py \
       --config /opt/waveplus_bridge/waveplus_bridge.yaml \
       --log ""
```

The log output will confirm if the bridge could successfully connect to the Wave Plus devices:

```
Read configuration file /opt/waveplus_bridge/waveplus_bridge.yaml
Configuration: 
   {'period': 120, 'sn': ['2930012345', '2931234569'], 'port': 80, 
    'csv': '/var/log/waveplus_bridge.csv', 'log': '', 
    'config': '/opt/waveplus_bridge/waveplus_bridge.yaml', 
    'name': {'2931234567': 'my_office', '2931234569': 'my_living'}}
 Data are logged to CSV file /var/log/waveplus_bridge.csv
 HTTP/Web server started on port 80
 Press ctrl+C to exit program!
 Device 2931234567 found, MAC address=a4:da:32:b9:53:c2
 Device 2931234569 found, MAC address=a4:da:32:b9:3f:b6
```

If the bridge has been successfully started, check if a connection to the HTTP/Web server can be established from a web browser (use address: http://<RaspberryPI_IP_Address>:<Port>).

Omit simply the --log argument to use the log file specified by the YAML configuration file.


## Setup the Wave Plus Bridge as a Service

Add the start/stop program provided by the Wave Plus Bridge package to the init.d directory and make it executable:

```
cd /etc/init.d/
sudo cp /opt/waveplus_bridge/init.d/waveplus_bridge .
sudo chmod 755 ./waveplus_bridge
```

Modify this start/stop program if necessary, for example to select a different YAML configuration file.

```
sudo nano ./waveplus_bridge
```

Add then the service to the system:

```
sudo update-rc.d waveplus_bridge defaults
```

Check if the start/stop script can be executed correctly :

```
sudo ./waveplus_bridge
-> Usage: /etc/init.d/waveplus_bridge {start|stop|restart|status}
```

```
 sudo ./waveplus_bridge start
-> [ ok ] Starting waveplus_bridge (via systemctl): waveplus_bridge.service.
```

```
 sudo ./waveplus_bridge stop
-> [ ok ] Stopping waveplus_bridge (via systemctl): waveplus_bridge.service.
```

Check if the service starts automatically after a reboot:

```
sudo reboot
```

If necessary, the service can be disabled:

```
sudo update-rc.d waveplus_bridge disable
```


# Raspberry Pi Installation

## Raspbian installation

The installation procedure is explained on this page: <https://www.raspberrypi.org/documentation/installation/installing-images/README.md>

Download latest Raspbian operating system from <https://www.raspberrypi.org/downloads/raspbian/>
Tested release 2019-09-26, full and lite versions.

Unzip the compressed image (e.g. with 7-Zip on Windows. Download: <https://www.7-zip.org/>)

Flash the image to a SD card, for example by using the Belena Etcher tool that is available on Windows, Linux and macOS. It can be downloaded here: <https://www.balena.io/etcher/> (version 1.5.57 has been tested on Windows).

The first connection can either happen by connecting monitor, keyboard and mouse to the Raspberry Pi, or connecting it via a cable to the network and accessing it via SSH. For this second option the SSH service can be enabled by adding an empty file called *ssh* to the boot sector of the SD card. This boot sector is accessible also on Windows (the SD card may need to be unplugged an plugged again to get it mounted).

Put the SD card into the Raspberry Pi and connect optionally monitor, keyboard and mouse to it.

Power up the Raspberry Pi.

If the connection is happening via SSH, search for the Raspberry using a network scanner (on Windows you can select one on: <https://www.pcwdld.com/best-free-ip-scanners-port-service-scannin>). Once the IP address has been identified, an SSH connection can be made via an SSH client (e.g. Kitty on Windows, download: <http://kitty.9bis.net/>.

Update system by running:

```
sudo apt update
sudo apt dist-upgrade
```

Setup optionally the network configuration (e.g. Wifi) and change the default password by running the system configuration tool:

```
sudo raspi-config
```

Ensure that the Bluetooth interface is enabled: 

```
sudo bluetoothctl
[bluetooth]# power on
[bluetooth]# exit
```

## Python Library Installation (Bullseye and before)

The Raspbian Buster and later, lite and full versions include both Python 3.7.3. However pip3, the Python Package Installer that is required to install additional packages is not pre-installed on the lite version. The following command will install it:

```
sudo apt install python3-pip
```
 
Install the Python3 packages that are missing to run the Wave Plus Bridge:

```
sudo pip3 install PyYAML
sudo pip3 install bluepy
sudo pip3 install paho-mqtt
```

## Python Library Installation (Bookworm and later)

The Raspberry Pi OS bookworm and later no longer allows globally installing Python libraries using pip.
The preferred approach is to create a virtualenv.


Use the following to create a virtualenv in the install directory.
```
python -m venv /opt/waveplus_bridge
```

To make sure you are working within the venv for this next step, activate it. This step is optional but it ensures your paths use the correct python binaries.

```
cd /opt/waveplus_bridge
source bin/activate
```

The prompt will change which shows activation was successful. Running `which python` will show the path to the binary is now your virtualenv: `/opt/waveplus_bridge/bin/python`.

Now install the prerequisites with the following command:

```
pip install -r requirements.txt
```

# Debugging

## Some simple checks

The following list may help you to find some frequent root causes:

* Check that the Raspberry Bluetooth interface is enabled: See last paragraph
  in section [Raspbian installation](#raspbian-installation).
* Ensure that all Python3 packages are installed: See last paragraph in section
  [Python Library Installation](#python-library-installation).
* Ensure that the communication between the Wave Plus bridge and the the Wave
  Plus device(s) work: Follow the instructions in section
  [Run the Wave Plus communication test application](#run-the-wave-plus-bridge-using-a-minimalist-configuration)
* Check the last lines in the log file (or standard output log) to find an
  indication about the encountered error.
* Ensure that the application (waveplus_bridge.py) is executable (chmod 775)
* Ensure that the provided serial numbers for the Wave Plus device(s) is/are
  correct.

## Run the Wave Plus communication test application

Instead of using the Wave Plus Bridge to validate and debug the communication
with a Wave Plus device, it may be easier to use just the 'waveplus.py' module
that is stored in the 'libs' folder. If it is launched standalone, this module
provides a minimalistic test application that reports any activities on the
standard output.

Run the 'waveplus.py' test application as root (required by the bluepy BLE
library), and provide as first argument the update period in seconds, followed
by one or multiple serial numbers of Wave Plus device(s):

```
sudo python waveplus.py <period> <serial_number_1> [serial_number_2] ..
```

That's all. The test application will continuously read the Wave Plus device
sensors in the specified interval. Check in the log that the communication to
the Wave Plus device(s) work well. Without having a stable communication, it
does not make sense to setup and run the full Wave Plus Bride application. You
should get a log similar to the following lines:

```
Setup device 2930031376
Setup device 2930089521
Entering into sensor read loop. Exit with Ctrl+C
+------------+------------+------------+------------+------------+------------+------------+------------+
|      Device|    humidity|    radon_st|    radon_lt| temperature|    pressure|         co2|         voc|
+------------+------------+------------+------------+------------+------------+------------+------------+
Reading sensor data for device 2930031376
Connect to 2930031376
  MAC address unknown, initialize scanning
    Run scan
    Run scan
      Found device 2930089521
    Run scan
      Found device None
    Run scan
    Run scan
      Found device 2930089521
    ...
    Run scan
      Found device None
      Found device 2930031376
  Device 2930031376 found, MAC address=a4:da:32:b9:53:c2
  -> {'humidity': 59.0, 'radon_st': 34, 'radon_lt': 46, 'temperature': 22.48, 'pressure': 896.14, 'co2': 552.0, 'voc': 59.0}
+------------+------------+------------+------------+------------+------------+------------+------------+
|  2930031376|        59.0|          34|          46|       22.48|      896.14|       552.0|        59.0|
+------------+------------+------------+------------+------------+------------+------------+------------+
Reading sensor data for device 2930089521
Connect to 2930089521
  Device 2930089521 previously found, MAC address=a4:da:32:b9:3f:b6
  -> {'humidity': 63.0, 'radon_st': 59, 'radon_lt': 45, 'temperature': 21.57, 'pressure': 895.58, 'co2': 583.0, 'voc': 56.0}
+------------+------------+------------+------------+------------+------------+------------+------------+
|  2930089521|        63.0|          59|          45|       21.57|      895.58|       583.0|        56.0|
+------------+------------+------------+------------+------------+------------+------------+------------+
Reading sensor data for device 2930031376
...
```

## Run the Wave Plus Bridge using a minimalist configuration

Perform your first trials with the Wave Plus Bridge application using a simple
configuration provided only as application argument, and not via a YAML
configuration file. No other arguments than one or multiple Wave Plus device
serial numbers are required to start the application. If no HTTP port and YAML
configuration file is specified, the Wave Plus Bridge application reports
detailed activities, which is useful to debug communication issues. Run the
application as root:

```
sudo python3 ./waveplus_bridge.py 2930031376 2930089521
```

This should lead to a similar log as shown in the following lines:

```
2022-06-23 22:20:41 -      __main__[   INFO] - Setup WavePlus device access
2022-06-23 22:20:41 -      __main__[   INFO] -   Done
2022-06-23 22:20:41 -      __main__[   INFO] - Start main loop. Press ctrl+C to exit program!
2022-06-23 22:20:41 -      __main__[  DEBUG] - Reading sensor data for device 2930031376
2022-06-23 22:20:46 -      __main__[  DEBUG] -   -> {'humidity': 59.5, 'radon_st': 34, 'radon_lt': 44, ...}
2022-06-23 22:20:46 -      __main__[  DEBUG] - Reading sensor data for device 2930089521
2022-06-23 22:20:48 -      __main__[  DEBUG] -   -> {'humidity': 63.0, 'radon_st': 59, 'radon_lt': 45, ...}
2022-06-23 22:22:41 -      __main__[  DEBUG] - Reading sensor data for device 2930031376
2022-06-23 22:22:43 -      __main__[  DEBUG] -   -> {'humidity': 59.5, 'radon_st': 34, 'radon_lt': 44, ...}

```

In case the Wave Plus Bridge does not work correctly at this stage, even more
detailed information has be reported by following the instructions provided in
section [Enable logging of additional debug information].

## Email and SMTP server configuration

This section provides some help in case emails are not sent correctly.

First of all, the mail settings should be tested by running the
'libs/threadedsendmail.py' module as script:

```
usage: python threadedsendmail.py [-h] [--port PORT] [--security SECURITY]
                                  [--user USER] [--password PASSWORD]
                                  [--subject SUBJECT] [--message MESSAGE]
                                  [--debug_level DEBUG_LEVEL] --server SERVER
                                  --to TO --from FROM

ThreadedSendMail demo and test

optional arguments:
  -h, --help            show this help message and exit
  --port PORT           SMTP server port, default=587
  --security SECURITY   SSL or TLS
  --user USER           Login user name
  --password PASSWORD   Login password
  --subject SUBJECT     Message subject
  --message MESSAGE     Message text
  --debug_level DEBUG_LEVEL
                        smtplib debug level. If > 0 threading is disabled.

required named arguments:
  --server SERVER       SMTP server address
  --to TO               To email list, separated with ','
  --from FROM           From address
```

So, refine the server and login credentials until an email is successfully
sent:

```
python libs/threadedsendmail.py \
        --server <SERVER> --port <PORT> --security <SECURITY> \
        --user <USER> --password <PASSWORD> \
        --from <FROM> --to <DESTINATION> \
        --debug_level 10 \
        --subject "Test" --message "This is a test"
```

And once this works, update the SMTP server and alert definitions in the YAML
file with the used arguments:

```
smtp_server:
    # Mail server address
    server: <SERVER>
    
    # Mail server port, e.g. 25, 465, 587
    port: <PORT>
    
    # Options: SSL, TLS, or no definition (default)
    security: <SECURITY>

    # Login user name
    user: <USER>

    # Login user password
    password: <PASSWORD>

alerts:
    -   sources:
            my_office:radon_st
        trigger:
            above: 150
            for: "00:30:00"
            min_interval: "01:00:00"
        actions:
            mail:
                from: <FROM>
                to: <DESTINATION>
```

## MQTT configuration

This section provides instructions how the MQTT server and device configuration can be debugged in case the expected messages are not successfully transferred to a subscriber.

First of all, it is recommended to run a generic MQTT client that allows exploring the message queues. Such tools are free available on the net (search for 'MQTT explorer').

The MQTT server/broker settings can then be checked by executing the demo application provided by the 'threadedmqttpublisher.py' module. The usage can be obtained by running it with the '-h' option:

```
python threadedmqttpublisher.py -h

usage: threadedmqttpublisher.py [-h] \
            --host HOST --topic_root TOPIC_ROOT 
            [--port PORT] [--client_id CLIENT_ID] [--auth AUTH] [--tls TLS] \
            [--will WILL] \
            [--debug_level DEBUG_LEVEL] \
            message_dicts [message_dicts ...]

positional arguments:
  message_dicts         Message dict: {<topic1>: <msg1>,..,<topic2>: <msg2>}

optional arguments:
  -h, --help            show this help message and exit
  --port PORT           MQTT broker host port, default=1883
  --client_id CLIENT_ID
                        Client ID
  --auth AUTH           Dict containing authentication parameters:
                        {username: <username>, password: <password>}
  --tls TLS             Dict containing client TLS configuration parameters:
                        {ca_certs: <ca_certs>, certfile: <certfile>,
                        keyfile: <keyfile>, tls_version: <tls_version>,
                        ciphers: <ciphers>, insecure: <bool>}
  --will WILL           Dict containing will parameters for the client:
                        {topic: <topic>, payload: <payload>, qos: <qos>,
                        retain=True
  --debug_level DEBUG_LEVEL
                        debug level. 0=no debug info,
                        3=max level of debug info

required named arguments:
  --host HOST           MQTT broker host address
  --topic_root TOPIC_ROOT
                        MQTT topic root

Remark:
    Dicts have to be provided in YAML format (auth, tls, will).

Example:
    python threadedmqttpublisher.py \
        --host test.mosquitto.org --port 1883 \
        --topic my_nice_home/waveplus_bridge \
        --will "{topic: my_nice_home/waveplus_bridge/status, \
                 payload: Offline}"
        "{status: Online}" \
        "{humidity: 61.5, radon_st: 35, temperature: 18.5}" \
        "{humidity: 66.5, radon_st: 38, temperature: 23.5}"
```

Once the  MQTT client receives messages, the settings can be ported into the YAML configuration file.


## Enable logging of additional debug information

To allow debugging connection issues as well as the application and library
code, the logging scheme is highly configurable via the YAML configuration
file.

The logging mechanism is based on the standard Python logging module, which
allows defining logging levels individually for the main Wave Plus Bridge
application as well as all the different libraries that are part of the
application.

The following section lists the loggers that are available for the main
application and the modules, together with their default logging level:

* \<root\> : Root logger (WARNING)
* \_\_main\_\_ : Main application logger (INFO)
* libs : Common library/module logger (WARNING)
* libs.waveplus : waveplus module logger (WARNING)
* libs.logdb : logdb module logger (WARNING)
* libs.threadedsendmail : threadedsendmail module logger (WARNING)
* libs.performancecheck : performancecheck module logger (WARNING)

If a log file is provided via the '--log' option of the main application or by
the YAML configuration file, a file handler is used to write log data.
Otherwise a stream handler is used to write the data to the standard output.

For a more sophisticated logging configuration, the 'log' statement of the YAML
configuration file can fully customize the logging scheme. See the Python
logging module documentation for details. The following example corresponds to
the selected settings if a simple log file is selected via the '--log' option.
It can be used as starting point for a customized logging scheme. Replace
simply the 'log' statement in the YAML configuration file by the following
lines.

```
log:
    version: 1
    formatters:
      default:
        format: '%(asctime)s - %(name)13s[%(levelname)7s] - %(message)s'
        datefmt: '%Y-%m-%d %H:%M:%S'
    handlers:
      file:
        level: DEBUG
        formatter: default
        class : logging.FileHandler
        filename: /var/log/waveplus_bridge.log
        encoding: utf8
        mode: a
    root:
      level: WARNING
      handlers: [file]
    loggers:
      __main__:
        level: INFO
      libs:
        level: WARNING
      # Configure additional loggers if required:
      # libs.waveplus:
      #   level: INFO
      # libs.logdb:
      # libs.threadedmqttpublisher:
      # libs.threadedsendmail:
      # libs.performancecheck:
```

For each module, a dedicated logging level can be selected out of the following
options: CRITICAL, ERROR, WARNING, INFO, DEBUG.

So, to log additional debug information of the main module, change simply the
corresponding debug level of the '__main__' logger:

```
      __main__:
        level: DEBUG
```

To log additional information of the waveplus module, like connection details:

```
      libs.waveplus:
        level: INFO
```

Or to log even more detailed debug information, change the previous lines into:

```
      libs.waveplus:
        level: DEBUG
```


# Related topics #

* [Correlation between Airthings Wave Plus and Corentium Plus Devices](https://github.com/Drolla/WavePlus_Bridge/wiki/Radon-Measurement-Correlation)
