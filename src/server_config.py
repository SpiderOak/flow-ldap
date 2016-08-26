"""
server_config.py

Config file functionality for semaphor-ldap server. 
"""

import threading
import logging
from ConfigParser import RawConfigParser

from src import utils


LOG = logging.getLogger("server_config")


class ServerConfig(object):
    """Loads the config from a cfg file."""

    def __init__(self, config_file_path):
        self.lock = threading.Lock()
        self.config_file_path = config_file_path
        self.config_dict = {}
        self.trigger_vars = {}
        self.sync_config()
        self.check_required_configs()

    def check_required_configs(self):
        """TODO: fail if required config values not present."""
        pass

    def register_trigger_for_var(self, var, func):
        """Register a callback to execute when 
        the given variable changes value.
        """
        self.lock.acquire()
        value = self.config_dict[var]
        self.trigger_vars[var] = (value, func)
        self.lock.release()

    def trigger_callbacks(self):
        """Execute callbacks for the registered 
        variables that changed value.
        """
        funcs_to_trigger = []
        self.lock.acquire()
        # detect changes in tracked variables
        for variable, value_func in self.trigger_vars.iteritems():
            current_config_value = self.config_dict[variable]
            if current_config_value != value_func[0]:
                funcs_to_trigger.append((variable, value_func[1]))
                self.trigger_vars[variable] = \
                    (current_config_value, value_func[1])
        self.lock.release()
        # run triggers
        for variable, func in funcs_to_trigger:
            LOG.debug(
                "triggering '%s' as '%s' variable value changed", 
                func.__name__, 
                variable,
            )
            func()

    def sync_config(self):
        """Load from config file into internal dict."""
        LOG.debug("sync config")
        cfg = RawConfigParser()
        cfg.read(self.config_file_path)
        self.lock.acquire()
        self.config_dict.update(utils.raw_config_as_dict(cfg).items()[0][1])
        self.lock.release()
        self.trigger_callbacks()

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
