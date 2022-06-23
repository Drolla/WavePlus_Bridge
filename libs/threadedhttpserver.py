"""Multi threaded HTTP/web server

This file implements a multi threaded HTTP/Web server. The port listening and
the request handler for each open socket is executed in an individual daemon
thread.

Copyright (C) 2020 Andreas Drollinger
See the file "LICENSE" for information on usage and redistribution of
this file, and for a DISCLAIMER OF ALL WARRANTIES.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread


class ThreadedHTTPServer(HTTPServer):
    """Multi threaded HTTP/web server class.

    This HTTP/web server class can be used in the same way as the standard
    class 'HTTPServer', but it generates for the HTTP port listener as well as
    for each HTTP connection a separate thread. This ensures that a main
    application is not affected timing wise by the HTTP server activities, and
    that also the different opened sockets are not interfering.
    """

    def __init__(self, *args):
        HTTPServer.__init__(self, *args)
        thread = Thread(target=self.serve_forever_on_other_thread)
        thread.daemon = True
        thread.start()

    def serve_forever_on_other_thread(self):
        try:
            self.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.server_close()

    def process_request(self, request, client_address):
        thread = Thread(
                target=self.__new_request,
                args=(self.RequestHandlerClass, request, client_address, self))
        thread.daemon = True
        thread.start()

    def __new_request(self, handlerClass, request, address, server):
        handlerClass(request, address, server)
        self.shutdown_request(request)


#############################################
# Main
#############################################

if __name__ == "__main__":
    import time

    # Change the following line to select a different port number
    DEMO_PORT_NUMBER = 8000

    # This class will handles any incoming request from the browser
    class myHandler(BaseHTTPRequestHandler):
        # Handler for the GET requests
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(
                    bytes("Hello World !<br>Time: " + str(int(time.time())),
                          "utf8"))
            return

    # Create the threaded server
    print('Starting HTTP server at port', DEMO_PORT_NUMBER, flush=True)
    server = ThreadedHTTPServer(('', DEMO_PORT_NUMBER), myHandler)

    # Stay in the wait loop
    while True:
        print('.', end='', flush=True)
        time.sleep(0.05)
