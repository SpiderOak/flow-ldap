"""
http_local_server.py

Local Semaphor-LDAP HTTP Server.
"""

import os
import logging
import threading
import binascii

from werkzeug.serving import ThreadedWSGIServer

from src import utils
from http_handler import HTTPRequestHandler


LOG = logging.getLogger("http_local_server")


class HTTPServer(object):
    """HTTP server container object. Runs the HTTP server loop."""

    @staticmethod
    def gen_auth_token():
        return binascii.hexlify(os.urandom(16))

    def __init__(self, server):
        self.server = server
        self.keep_running = threading.Event()
        self.keep_running.set()
        self.auth_token = self.gen_auth_token()
        self.listen_port = self.server.config.get("listen-port")
        app = HTTPRequestHandler(self.server, self)
        try:
            self.wsgi_server = ThreadedWSGIServer(
                utils.LOCAL_SERVER_HOST,
                self.listen_port, 
                app,
            )
        except Exception as exception:
            LOG.error("Failed to start HTTP server: '%s'", exception)
            raise
        self.wsgi_server.timeout = 1

    def run(self):
        """Run this HTTP server."""
        while self.keep_running.is_set():
            self.wsgi_server.handle_request()
        self.wsgi_server.server_close()
