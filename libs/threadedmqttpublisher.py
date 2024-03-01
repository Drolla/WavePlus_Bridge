"""Threaded MQTT client to publish messages

This file implements a threaded MQTT client class. It is based on the
threadding support provided by the paho.mqtt.client module.

Copyright (C) 2023 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import time
import logging
import paho.mqtt.client as mqtt_client

logger = logging.getLogger(__name__)


class ThreadedMqttPublisher:
    """Threaded MQTT client to publish messages.

    This class implements a threaded MQTT client and expose a method to publish
    messages. The opened connection to the MQTT broker is persistent.

    The constructor accepts all the connection options provided by the Paho
    MQTT client publish methods 'single' and 'multiple'. In addition to these
    methods, LWT ('will' argument) is properly taken into account by the broker
    since the connection is persistent.

    Args:
        hostname (string): FQDN or IP4 or IP6 address of the broker
        port (integer): Port to connect to the broker on. default=1883
        keepalive (integer): Timeout value for the client in seconds.
                default=60
        bind_address (string): default=""
        client_id (string): MQTT client id to use. If "" (default) or None, the
                Paho library will generate a client id automatically.
        protocol (integer): Defines the MQTT protocol version. Use either
                MQTTv31 (default) or MQTTv311.
        transport (string): Defines the transport layer that has to be either
                "tcp" (default) or 'websockets'.
        auth (dict): Dict containing authentication parameters for the client:
                auth = {'username':"<username>", 'password':"<password>"}
                Username is required, password is optional and will default to
                None if not provided. Defaults to None, which indicates no
                authentication is to be used.
        tls (dict): Dict containing TLS configuration parameters for the
                client:
                dict = {'ca_certs':"<ca_certs>", 'certfile':"<certfile>",
                        'keyfile':"<keyfile>", 'tls_version':"<tls_version>",
                        'ciphers':"<ciphers">, 'insecure':"<bool>"}
                ca_certs is required, all other parameters are optional and
                will default to None if not provided, which results in the
                client using the default behaviour - see the paho.mqtt.client
                documentation.
                Alternatively, tls input can be an SSLContext object, which
                will be processed using the tls_set_context method.
                Defaults to None, which indicates that TLS should not be used.
        will (dict): Dict containing will parameters for the client:
                will = {'topic': "<topic>", 'payload':"<payload">, 'qos':<qos>,
                        'retain':<retain>}.
                Topic is required, all other parameters are optional and will
                default to None, 0 and False respectively. Defaults to None,
                which indicates no will should be used.
        proxy_args (dict): Dictionary given to the client. Default=None

    Example:
        mqtt_publisher = ThreadedMqttPublisher(
                hostname="test.mosquitto.org",
                port=1883,
                will={'topic': "my_nice_home/office/status",
                      'payload':"Offline"}
        )
        mqtt_publisher.publish_single(
                "my_nice_home/office/status", "Online")
        mqtt_publisher.publish_multiple(
                "my_nice_home/office",
                [{"topic": "status", "payload": "Online"},
                 {"topic": "humidity", "payload": 61.5},
                 {"topic": "temperature", "payload": 18.5}]
        )
    """

    def __init__(self,
                 hostname, port=1883, keepalive=60, bind_address="",
                 client_id="", protocol=mqtt_client.MQTTv311, transport="tcp",
                 auth=None, tls=None,
                 will=None, proxy_args=None):

        # Store the configuration for later use
        self.config = locals()

        # Create the MQTT client. Add the new argument 'callback_api_version'
        # for the client version >=2.0.
        mqtt_client_args = dict(
                client_id=self.config["client_id"],
                protocol=self.config["protocol"],
                transport=self.config["transport"]
        )
        try:
            mqtt_client_args.update(dict(
                callback_api_version=mqtt_client.CallbackAPIVersion.VERSION1
            ))
        except AttributeError:
            pass
        mqttc = mqtt_client.Client(**mqtt_client_args)
        self.mqttc = mqttc
        mqttc.enable_logger()
        logger.debug("ThreadedMqttPublisher: Connect to %s", hostname)

        # Apply proxy, authentication, will and TLS configurations: This
        # section is mainly a copy from the 'multiple' method of the Paho MQTT
        # client's publish module.

        if self.config["proxy_args"] is not None:
            mqttc.proxy_set(**self.config["proxy_args"])

        if self.config["auth"]:
            username = self.config["auth"].get('username')
            if username:
                password = self.config["auth"].get('password')
                mqttc.username_pw_set(username, password)
            else:
                raise KeyError("The 'username' key was not found, this is "
                               "required for auth")

        if self.config["will"] is not None:
            mqttc.will_set(**self.config["will"])

        if self.config["tls"] is not None:
            if isinstance(self.config["tls"], dict):
                insecure = self.config["tls"].pop('insecure', False)
                mqttc.tls_set(**self.config["tls"])
                if insecure:
                    # Must be set *after* the `mqttc.tls_set()` call since it
                    # sets up the SSL context that `mqttc.tls_insecure_set`
                    # alters.
                    mqttc.tls_insecure_set(insecure)
            else:
                # Assume input is SSLContext object
                mqttc.tls_set_context(self.config["tls"])

        # Define the connection. The connection will be later performed by the
        # loop_forever method that retries creating a connection until the
        # broker responds.
        mqttc.connect_async(
                host=self.config["hostname"],
                port=self.config["port"],
                keepalive=self.config["keepalive"],
                bind_address=self.config["bind_address"],
        )

        # Start the loop in another thread.
        mqttc.loop_start()

    def stop(self):
        """Stops the network thread and the connection

        Call preferably this function to stop the connection instead of
        deleting the object instance to ensure a controlled disconnection.
        """

        # Ignore this command if the mqttc object is already deleted (=None)
        if self.mqttc is None:
            return

        logger.debug("ThreadedMqttPublisher: Disconnect and stop")
        self.mqttc.loop_stop()
        self.mqttc.disconnect()
        del self.mqttc
        self.mqttc = None

    def __del__(self):
        self.stop()

    def publish_single(
            self, topic, payload=None, qos=0, retain=False, properties=None):
        """Publish a single message to a broker."""

        logger.debug("  publish_single %s: %s", topic, payload)
        publish_result = self.mqttc.publish(
                topic, payload, qos, retain, properties)
        logger.debug("  -> %s", str(publish_result))
        return publish_result

    def publish_multiple(self, messages, topic_root=""):
        """Publish multiple messages to a broker."""

        logger.debug("publish_multiple %s: %s", topic_root, str(messages))
        for message in messages:
            topic = "/".join(filter(bool, [topic_root, message["topic"]]))
            payload = message["payload"]
            qos = message["qos"] if "qos" in message else 0
            retain = message["retain"] if "retain" in message else False
            prop = message["prop"] if "prop" in message else None
            publish_result = self.publish_single(
                    topic, payload, qos, retain, prop)
        return publish_result


#############################################
# Main
#############################################

# Small module demo that can also be used to check the connection to the
# MQTT server.

if __name__ == "__main__":
    import argparse
    import yaml
    import textwrap

    class DescriptionHelpFormatter(argparse.RawDescriptionHelpFormatter):
        def _fill_text(self, text, width, indent):
            return textwrap.dedent(text)

    # Define and parse the arguments
    parser = argparse.ArgumentParser(
            formatter_class=DescriptionHelpFormatter,
            description="ThreadedMqttPublisher demo and test application",
            epilog="""
                Remark:
                    Dicts have to be provided in YAML format (auth, tls, will).

                Example:
                    python threadedmqttpublisher.py \\
                        --host test.mosquitto.org --port 1883 \\
                        --topic my_nice_home/waveplus_bridge \\
                        --will "{topic: my_nice_home/waveplus_bridge/status, \\
                                 payload: Offline}"
                        "{status: Online}" \\
                        "{humidity: 61.5, radon_st: 35, temperature: 18.5}" \\
                        "{humidity: 66.5, radon_st: 38, temperature: 23.5}"
            """
    )

    parser.add_argument(
            "--port", type=int, default=1883,
            help="MQTT broker host port, default=1883")
    parser.add_argument(
            "--client_id", type=str, default="", help="Client ID")
    parser.add_argument(
            "--auth", type=str, default=None,
            help="Dict containing authentication parameters: "
                 "{username: <username>, password: <password>}")
    parser.add_argument(
            "--tls", type=str, default=None,
            help="Dict containing client TLS configuration parameters: "
                 "{ca_certs: <ca_certs>, certfile: <certfile>, "
                 "keyfile: <keyfile>, tls_version: <tls_version>,"
                 "ciphers: <ciphers>, insecure: <bool>}")
    parser.add_argument(
            "--will", type=str, default=None,
            help="Dict containing will parameters for the client: "
                 "{topic: <topic>, payload: <payload>, qos: <qos>, "
                 "retain=True")
    parser.add_argument(
            "--debug_level", type=int, default=1,
            help="debug level. 0=no debug info, 3=max level of debug info")

    required_args = parser.add_argument_group('required named arguments')

    required_args.add_argument(
            "--host", type=str, help="MQTT broker host address", required=True)
    required_args.add_argument(
            "--topic_root", type=str, help="MQTT topic root", required=True)
    parser.add_argument(
            'message_dicts', metavar='message_dicts', type=str, nargs='+',
            help='Message dict: {<topic1>: <msg1>,..,<topic2>: <msg2>}')
    config = vars(parser.parse_args())

    # Configure the logger
    if config["debug_level"]:
        log_formatter = logging.Formatter(
                '%(name)s - %(levelname)s - %(message)s')
        log_handler = logging.StreamHandler()
        log_handler.setLevel(logging.DEBUG)
        log_handler.setFormatter(log_formatter)
        logger.addHandler(log_handler)
        logger.setLevel(logging.INFO)
    if config["debug_level"] > 1:
        logger.setLevel(logging.DEBUG)
    if config["debug_level"] > 2:
        mqtt_logger = logging.getLogger("paho.mqtt.client")
        mqtt_logger.addHandler(log_handler)
        mqtt_logger.setLevel(logging.DEBUG)

    # Argument processing
    logger.info("Parse arguments provided in Yaml format")
    for dict_var_index in ("auth", "tls", "will"):
        if config[dict_var_index] is not None:
            config[dict_var_index] = yaml.load(config[dict_var_index],
                                               Loader=yaml.SafeLoader)
    # Launch ThreadedMqttPublisher 
    logger.info("Start ThreadedMqttPublisher:")
    for cfg_index in config:
        logger.info("  %s: %s", cfg_index, str(config[cfg_index]))

    mqtt_publisher = ThreadedMqttPublisher(
            hostname=config["host"],
            port=config["port"],
            client_id=config["client_id"],
            auth=config["auth"],
            tls=config["tls"],
            will=config["will"]
    )
    time.sleep(1)

    # Publish all the data 
    for message_str in config["message_dicts"]:
        logger.info("Publish data: %s ...", message_str)
        messages = []
        for topic, payload in yaml.load(message_str,
                                        Loader=yaml.SafeLoader).items():
            messages.append({"topic": topic, "payload": payload})
        mqtt_publisher.publish_multiple(messages, config["topic_root"])
        logger.info("... done")
        time.sleep(3)

    logger.info("Disconnect")
    mqtt_publisher.stop()
    time.sleep(2)

    logger.info("Exit")
