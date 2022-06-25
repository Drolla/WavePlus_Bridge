"""Wave Plus Bridge MQTT publisher testing

This program tests the MQTT publisher class provided by the Wave Plus Bridge
application. It uses server defined in the test_configuration.yaml file.

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

sys.path.append("..")
import waveplus_bridge

# Read the configuration
with open("test_configuration.yaml", "r") as yamlfile:
    mqtt_config = yaml.load(yamlfile, Loader=yaml.SafeLoader)["mqtt"]

print("MQTT server configuration:")
print("  Host:", mqtt_config["host"], "port:", mqtt_config["port"])
print("  Topic:", mqtt_config["topic"])

# Create the data structure
print("MQTT messages:")
data = {}
for device in mqtt_config["publish"].keys():
    data[device] = {
        key: round(value,1) for (key, value) in {
            'humidity': random.uniform(20.0, 80.0),
            'radon_st': random.uniform(30, 120),
            'radon_lt': random.uniform(30, 120),
            'temperature': random.uniform(17, 24),
            'pressure': random.uniform(700, 900),
            'co2': random.uniform(500, 800),
            'voc': random.uniform(100, 900),
        }.items()
    }
    print("  ", device, ":", ", ".join(
            [key + "=" + str(value) for key, value in data[device].items()]))

# Create an MQTT publisher instance, and publish some messages
print("Publish the messages on the MQTT server")
mqtt_publisher = waveplus_bridge.MqttPublisher(mqtt_config)
mqtt_publisher.publish(data)
print("Done")
