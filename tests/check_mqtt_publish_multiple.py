"""Test of the paho.mqtt.publish.multiple method

This program tests the paho.mqtt.publish.multiple method, by using the server
definitions provided by the test_configuration.yaml file.

Copyright (C) 2022 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import yaml
import sys
import random

try:
    import paho.mqtt.client as mqtt_client
    import paho.mqtt.publish as mqtt_publish
except Exception as err:
    print("MQTT service is not available:", err)

# Read the configuration
with open("test_configuration.yaml", "r") as yamlfile:
    mqtt_config = yaml.load(yamlfile, Loader=yaml.SafeLoader)["mqtt"]

print("MQTT server configuration:")
print("  Host:", mqtt_config["host"], "port:", mqtt_config["port"])
print("  Topic:", mqtt_config["topic"])

# Create the data structure
msgs = [
    {"topic": mqtt_config["topic"] + "/test1/multiple",
            "payload": "multiple 1"},
    (mqtt_config["topic"] + "/test2/multiple", "multiple 2", 0, False)
]

# Perform the publishing
mqtt_publish.multiple(
        msgs,
        hostname=mqtt_config["host"], port=mqtt_config["port"],
        client_id="", keepalive=60, will=None, auth=None,
        tls=None, protocol=mqtt_client.MQTTv31)
