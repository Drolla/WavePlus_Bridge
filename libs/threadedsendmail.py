"""Threaded mail sender

This class implements a mail transmission service running on another thread. It
supports optionally SSL and TLS encryption.

Eventual connection issues to the SMTP mail server can be debugged by running
this module standalone. Comprehensive information about how running the script
is provided via the '-h' option:

Usage: threadedsendmail.py [-h] [--port PORT] [--security SECURITY]
                           [--user USER] [--password PASSWORD]
                           [--subject SUBJECT] [--message MESSAGE]
                           [--debug_level DEBUG_LEVEL] --server SERVER --to TO
                           --from FROM

Optional arguments:
  -h, --help            show this help message and exit
  --port PORT           SMTP server port, default=587
  --security SECURITY   SSL or TLS
  --user USER           Login user name
  --password PASSWORD   Login password
  --subject SUBJECT     Message subject
  --message MESSAGE     Message text
  --debug_level DEBUG_LEVEL
                        smtplib debug level. If > 0 threading is disabled.

Required named arguments:
  --server SERVER       SMTP server address
  --to TO               To email list, separated with ','
  --from FROM           From address

Example:
    python ../libs/threadedsendmail.py \
        --server mail.server.com --port 465 --security SSL \
        --user wave@plus.com --password bridge123 \
        --from wave.plus@myhome.com --to olivia.brown@family.com \
        --subject Warning --message "Sensor high value detected!" \
        --debug_level 1

Copyright (C) 2020 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

import time
from threading import Thread
import queue
import smtplib
from email.message import EmailMessage
import logging

logger = logging.getLogger(__name__)


class ThreadedSendMail:
    """Simple threaded class to send mails

    The constructor has various parameters to define the SMTP server
    information and credentials. It creates a new thread that is used to send
    email messages that are initiated via the method 'send_mail'.


    Args:
        server (string): SMTP mail server address
        port (integer): SMTP mail server port, default=587
        security (string): Security settings. Options: SSL, TLS, or no
                definition (default)
        user (string): Login user name (optional argument)
        password (string): Login user password (optional argument)
        debug_level (integer): Optional parameter. Used for debugging purposes.
                The value is used to define the debug levels of the SMTP and
                SMTP_SSL classes of the smtplib module. 0 disables debug
                outputs (default). If non-0, the module will work in a
                non-threaded way.

    Example:
        sm = threadedsendmail.ThreadedSendMail(
                server="mail.server.com",
                port=465,
                security="SSL",
                user="wave@plus.com",
                password="bridge123")

        sm.send_mail(
                "wave.plus@myhome.com",
                "liam.smith@family.com",
                "Sensor alert",
                "Sensor triggered high measurement data!")
    """

    TIMEOUT = 1

    def __init__(self,
                 server, port=587, security=None, user=None, password=None,
                 debug_level=0):
        self.server = server
        self.port = port
        self.security = security
        self.user = user
        self.password = password
        self.debug_level = debug_level

        # Enable threaded mode only in non-debug mode
        if debug_level == 0:
            self.queue = queue.Queue()
            thread = Thread(target=self._queue_handler)
            thread.daemon = True
            thread.start()

    # See: https://stackoverflow.com/questions/19033818/how-to-call-a-
    #      function-on-a-running-python-thread
    def send_mail(self, from_address, to_address, subject, message):
        """Mail send message user command

        Add the mail send command to the thread queue in threaded mode.
        Otherwise launch the mail send command directly.
        """

        if self.debug_level == 0:
            self.queue.put((self._send_mail,
                            [from_address, to_address, subject, message], {}))
        else:
            self._send_mail(from_address, to_address, subject, message)

    def _queue_handler(self):
        """Thread queue handler"""

        while True:
            try:
                function, args, kwargs = self.queue.get(timeout=self.TIMEOUT)
                function(*args, **kwargs)
                self.queue.task_done()
            except queue.Empty:
                pass
            except Exception as err:
                logger.exception("  Stack trace:")

    def _send_mail(self, from_address, to_address, subject, message):
        """Send mail service

        Unless executed in debug mode, this method is executed in the separate
        thread. It establish connection to the SMTP server using optional
        encryption modes, and sends then the message to this server.
        """

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = from_address
        if isinstance(to_address, list):
            msg['To'] = ', '.join(to_address)
        else:
            msg['To'] = to_address
        msg.set_content(message)

        if self.security == "SSL":
            srv = smtplib.SMTP_SSL(self.server, self.port)
            srv.set_debuglevel(self.debug_level)
        else:
            srv = smtplib.SMTP(self.server, self.port)
            srv.set_debuglevel(self.debug_level)
            if self.security == "TLS":
                srv.ehlo()
                srv.starttls()
                srv.ehlo()

        if self.user is not None and self.password is not None:
            srv.login(self.user, self.password)

        srv.send_message(msg)
        srv.quit()
        logger.info("Message sent to %s: %s", to_address, subject)


#############################################
# Main
#############################################

# Self test and SMTP mail server connection debugging. See file header for
# details.

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
            description="ThreadedSendMail demo and test")

    parser.add_argument(
            "--port", type=int, help="SMTP server port, default=587",
            default=587)
    parser.add_argument(
            "--security", type=str, help="SSL or TLS", default=None)
    parser.add_argument(
            "--user", type=str, help="Login user name", default=None)
    parser.add_argument(
            "--password", type=str, help="Login password", default=None)
    parser.add_argument(
            "--subject", type=str, default="", help="Message subject")
    parser.add_argument(
            "--message", type=str, default="", help="Message text")
    parser.add_argument(
            "--debug_level", type=int, default=0,
            help="smtplib debug level. If > 0 threading is disabled.")

    required_args = parser.add_argument_group('required named arguments')
    required_args.add_argument(
            "--server", type=str, help="SMTP server address", required=True)
    required_args.add_argument(
            "--to", type=str, help="To email list, separated with ','",
            required=True)
    required_args.add_argument(
            "--from", type=str, help="From address", required=True)

    config = vars(parser.parse_args())
    print('config:', config)

    sm = ThreadedSendMail(
            server=config["server"], port=config["port"],
            security=config["security"],
            user=config["user"], password=config["password"],
            debug_level=config["debug_level"])

    sm.send_mail(
            config["from"], config["to"],
            config["subject"], config["message"])

    if config["debug_level"] == 0:
        sm.queue.join()
        print("Main: Queue is empty")
        time.sleep(2)
