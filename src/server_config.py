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
[Semaphor LDAP Server]
########################################
# Generic
listen-address = localhost
listen-port = 8080
db-backup-minutes = 60
ldap-sync-minutes = 60
excluded-accounts = 
ldap-sync-on = no
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
dir-fname-source = givenName
dir-lname-source = sn
dir-guid-source = objectGUID
dir-auth-source = dn
"""


def create_config_file(config_file_path):
    """Creates a config file with default values."""
    buf = StringIO.StringIO(_DEFAULT_CONFIG)
    cfg = RawConfigParser()
    cfg.readfp(buf)
    with open(config_file_path, "w") as config_file:
        cfg.write(config_file)


class ServerConfig(object):
    """Loads the config from a cfg file."""

    def __init__(self, config_file_path):
        self.lock = threading.Lock()
        self.config_file_path = config_file_path
        self.config_dict = {}
        self.sync_config()
        self.check_required_configs()

    def check_required_configs(self):
        """TODO: fail if required config values not present."""
        pass

    def sync_config(self):
        """Load from config file into internal dict."""
        LOG.debug("sync config")
        cfg = RawConfigParser()
        cfg.read(self.config_file_path)
        self.lock.acquire()
        self.config_dict.update(utils.raw_config_as_dict(cfg).items()[0][1])
        self.lock.release()

    def get(self, var):
        self.lock.acquire()
        value = self.config_dict.get(var)
        self.lock.release()
        return value

    def get_list(self, var):
        ret_list = []
        value = self.get(var)
        if value:
            ret_list = value.strip(" \n").split("\n")
        return ret_list   

