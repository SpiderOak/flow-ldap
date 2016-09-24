"""
http.py

HTTP handling for server and CLI communication
"""

import logging
import inspect

from src import utils
from src.log import app_log


LOG = logging.getLogger("http_api")


class HttpApi(object):
    """HTTP API for this application.
    Public methods defined here are exposed as HTTP API methods,
    and they are also exposed as command line
    arguments on the client
    These methods must:
      - Contain a docstring with the following format:
      '''One line description
      More doc can be added here
      ...
      Arguments:
      arg1 : one line description for arg1.
      arg2 : one line description for arg2.
      '''
      - Method must be public (does not start with _)
      - Method must return a result that can be
        converted to string
    """

    def __init__(self, server, http_server):
        self.server = server
        self.ldap_factory = self.server.ldap_factory
        self.dma_manager = self.server.dma_manager
        self.http_server = http_server

    def create_account(self, dmk):
        """Creates the Directory Management Account.
        It returns the generated username and recovery key.
        Arguments:
        dmk : Directory Management Key.
        """
        if not dmk:
            raise Exception("Empty dmk.")
        try:
            response = self.dma_manager.create_dma_account(dmk)
        except Exception as exception:
            # Needed because json cannot handle requests.RequestException
            raise Exception(str(exception))
        return response

    def create_device(self, username, recovery_key):
        """Creates a new device for the DMA.
        Arguments:
        username : Flow DMA username.
        recovery-key : Flow DMA recovery key.
        """
        if not username or not recovery_key:
            raise Exception("Empty username/recovery key")
        self.dma_manager.create_device(username, recovery_key)
        return "null"

    def group_userlist(self):
        """Returns the userlist for the configured Group/OU."""
        ldap_conn = self.ldap_factory.get_connection()
        ldap_group = ldap_conn.get_group(self.server.config.get("group-dn"))
        users = ldap_group.userlist()
        ldap_conn.close()
        return users

    def log_dest(self, target):
        """Configures the server's logging destination.
        Arguments:
        target : {syslog,event,file,null}.
        """
        if target not in app_log.supported_log_destinations():
            raise Exception("Logging destination not supported on platform")
        self.server.config.set_key_value("log-dest", target)
        return "null"

    def config_list(self):
        """Returns a list with the current server configuration."""
        return self.server.config.get_key_values()

    def config_set(self, key, value):
        """Returns a list with the current server configuration.
        Arguments:
        key : Name of the configuration variable to set.
        value : Value of the configuration variable to set.[optional]
        """
        self.server.config.set_key_value(key, value)
        return "null"

    def ldap_sync_enable(self):
        """Enable LDAP sync scheduled run."""
        self.server.config.set_key_value("ldap-sync-on", "yes")
        return "null"

    def ldap_sync_disable(self):
        """Disable LDAP sync scheduled run."""
        self.server.config.set_key_value("ldap-sync-on", "no")
        return "null"

    def check_status(self):
        """Executes health checks and returns the server status."""
        try:
            self.server.db.check_connection()
        except Exception as exception:
            db_state = "ERROR: %s" % str(exception)
        else:
            db_state = "OK"
        try:
            self.dma_manager.check_flow_connection()
        except Exception as exception:
            flow_state = "ERROR: %s" % str(exception)
        else:
            flow_state = "OK"
        try:
            self.ldap_factory.check_connection()
        except Exception as exception:
            ldap_state = "ERROR: %s" % str(exception)
        else:
            ldap_state = "OK"
        sync_state = "ON" \
            if self.server.ldap_sync_on.is_set() else "OFF"
        if self.server.ldap_sync.lock.locked():
            sync_state += ", running..."
        return {
            "db": db_state,
            "flow": flow_state,
            "ldap": ldap_state,
            "sync": sync_state,
        }

    def dma_fingerprint(self):
        """Returns the DMA fingerprint."""
        return self.dma_manager.get_dma_fingerprint()

    def db_userlist(self):
        """Returns all the accounts on the local DB."""
        accounts = self.server.db.get_db_accounts()
        return accounts

    def ldap_sync_trigger(self):
        """Triggers an LDAP sync (if enabled)."""
        self.server.ldap_sync.trigger_sync()
        return "null"

    def server_version(self):
        """Returns the version of the running server."""
        return "%s,backend=%s" % (
            utils.VERSION,
            self.dma_manager.flow.build_number(),
        )

    @classmethod
    def get_apis(cls):
        """Helper class method to get all HTTP API method names.
        Returns a list of tuples with (method_name, function object)
        """
        methods = inspect.getmembers(cls, predicate=inspect.ismethod)
        api_methods = []
        for name, method in methods:
            if not name.startswith("_") and \
                    name != "get_apis" and name != "get_api_args":
                api_methods.append((name, method))
        return api_methods

    @classmethod
    def get_api_args(cls, method_name):
        """Helper class method to return
        the argument names of a given function name.
        Arguments:
        method_name : string
        Returns a list with the function argument names.
        """
        func = getattr(cls, method_name)
        args = inspect.getargspec(func).args
        args.remove("self")
        return args
