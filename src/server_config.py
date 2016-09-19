"""
server_config.py

Config file functionality for semaphor-ldap server.
"""

import threading
import logging
from ConfigParser import RawConfigParser
import StringIO

from src import utils


LOG = logging.getLogger("server_config")
_DEFAULT_CONFIG = """
[%s]
########################################
# Generic
listen-port = 8080
db-backup-minutes = 60
ldap-sync-minutes = 60
excluded-accounts =
ldap-sync-on = no
verbose = no
log-dest =
########################################
# LDAP
uri = ldap://domain.com
base-dn = dc=domain,dc=com
admin-user = cn=admin,dc=domain,dc=com
admin-pw = password
group-dn = ou=People,dc=domain,dc=com
########################################
# LDAP Vendor
server-type = AD
dir-member-source = member
dir-username-source = userPrincipalName
dir-guid-source = objectGUID
dir-auth-source = dn
""" % (
    utils.SERVER_CONFIG_SECTION,
)
LDAP_VARIABLES = set([
    "uri", "base-dn", "admin-user", "admin-pw", "group-dn",
    "server-type", "dir-member-source", "dir-username-source",
    "dir-guid-source", "dir-auth-source",
])
_LDAP_CONFIG_GROUP_NAME = "LDAP Config"
_SERVER_CONFIG_GROUP_NAME = "Server Config"


def create_config_file(config_file_path):
    """Creates a config file with default values."""
    buf = StringIO.StringIO(_DEFAULT_CONFIG)
    cfg = RawConfigParser()
    cfg.readfp(buf)
    with open(config_file_path, "w") as config_file:
        cfg.write(config_file)


class ServerConfig(object):
    """Loads the config from a cfg file."""

    def __init__(self, server, config_file_path):
        self.server = server
        self.lock = threading.Lock()
        self.config_file_path = config_file_path
        self.config_dict = {}
        self.trigger_callbacks = {}
        self.sync_config()

    def sync_config(self):
        """Load from config file into internal dict."""
        LOG.info("sync config")
        cfg = RawConfigParser()
        cfg.read(self.config_file_path)
        self.lock.acquire()
        self.config_dict.update(utils.raw_config_as_dict(cfg).items()[0][1])
        self.lock.release()

    def get(self, var):
        """Returns the value for the given config variable name."""
        self.lock.acquire()
        value = self.config_dict.get(var)
        self.lock.release()
        return value

    def get_list(self, var):
        """Returns the value for the given config variable name as a list.
        Currently used for 'excluded-accounts' config.
        """
        ret_list = []
        value = self.get(var)
        if value:
            ret_list = value.replace(" ", "").split(",")
        return ret_list

    def get_key_values(self):
        """Returns the current configuration values for all variables."""
        self.lock.acquire()
        ret_config_dict = {
            _SERVER_CONFIG_GROUP_NAME: {},
            _LDAP_CONFIG_GROUP_NAME: {},
        }
        for key, value in self.config_dict.items():
            if key in LDAP_VARIABLES:
                ret_config_dict[_LDAP_CONFIG_GROUP_NAME][key] = value
            else:
                ret_config_dict[_SERVER_CONFIG_GROUP_NAME][key] = value
        self.lock.release()
        return ret_config_dict

    def register_callback(self, variables_iter, trigger_func):
        """Registers the given trigger_func to be executed when
        the variables in variables_iter are updated.
        """
        self.lock.acquire()
        for variable in variables_iter:
            self.trigger_callbacks[variable] = trigger_func
        self.lock.release()

    def store_config(self):
        """Saves the current configuration to a cfg file."""
        LOG.info("storing config")
        cfg = RawConfigParser()
        cfg.add_section(utils.SERVER_CONFIG_SECTION)
        for key, value in self.config_dict.items():
            cfg.set(utils.SERVER_CONFIG_SECTION, key, value)
        with open(self.config_file_path, "w") as config_file:
            cfg.write(config_file)

    def set_key_value(self, key, value):
        """Updates the value of the given key.
        It triggers the registered triggers and also stores the config
        to a file after the update.
        """
        self.lock.acquire()
        if key not in self.config_dict:
            self.lock.release()
            raise Exception("'%s' not a valid config variable" % key)
        self.config_dict.update({key: value})
        trigger_func = self.trigger_callbacks.get(key)
        self.store_config()
        self.lock.release()
        if trigger_func:
            trigger_func()
