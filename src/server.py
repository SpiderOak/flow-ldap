"""
server.py

Server mode source code.
"""

import sys
import os
from ConfigParser import RawConfigParser
import logging
import time
import threading

import schedule

import common
import flow
import ldap_reader
import http


SERVER_CONFIG = "Server"
LDAP_MAIN_CONFIG_SECTION = "LDAP"
LDAP_VENDOR_CONFIG_SECTION = "LDAP Vendor"
FLOW_CONFIG_SECTION = "Flow"

LOG = logging.getLogger("server")


class Server(object):
    """Runs the server mode for this application."""

    def __init__(self, options):
        self.debug = options.debug
        self.initialized = False
        self.flow = None
        self.ldap_conn = None
        self.http_server = None
        self.server_config = {}  # config_var -> config_value
        self.ldap_config = {}  # config_var -> config_value
        self.ldap_vendor_config = {}  # config_var -> config_value
        self.flow_config = {}  # config_var -> config_value
        self.read_config(options.config)

        self.init_ldap()
        self.init_flow()
        self.init_cron()
        self.init_http()

        self.cron_thread = threading.Thread(target=self.run_cron, args=())
        self.loop_cron = threading.Event()
        self.flow_thread = threading.Thread(target=self.run_flow, args=())
        self.loop_flow = threading.Event()
        self.threads_running = False

        config_written = self.write_config()
        if config_written:
            self.initialized = True

        LOG.info("server initialized")

        # Commented out for now
        # LOG.info("going daemon")
        # self.daemonize()

    def read_config(self, config_file):
        """Load config sections from a config file into dicts.
        Arguments:
        config_file : string, file name
        """
        cfg = RawConfigParser()
        cfg.read(config_file)
        config_dict = common.raw_config_as_dict(cfg)
        self.ldap_config = config_dict[
            LDAP_MAIN_CONFIG_SECTION]
        self.ldap_vendor_config = config_dict[
            LDAP_VENDOR_CONFIG_SECTION]
        self.flow_config = config_dict[
            FLOW_CONFIG_SECTION]
        self.server_config = config_dict[
            SERVER_CONFIG]

    def init_cron(self):
        """Initializes the cron configuration for this application."""
        minutes = int(self.ldap_config["poll_group_minutes"])
        schedule.every(minutes).minutes.do(self.group_userlist)

    def init_ldap(self):
        """Initializes LDAP from config values."""
        self.ldap_conn = ldap_reader.LdapConnection(
            self.ldap_config["uri"],
            self.ldap_config["base_dn"],
            self.ldap_config["admin_dn"],
            self.ldap_config["admin_pw"],
            self.ldap_vendor_config)

    def init_flow(self):
        """Initializes Flow instance from config info.
        - If the account does not exist, it creates the account + a device.
        - If the account exists, but there's no device, it creates a device.
        - If the account and device already exist, it will use them.
        """
        self.flow = flow.Flow()
        # Try to start_up first, an account+device may already be created
        try:
            self.flow.start_up(self.flow_config["username"])
            LOG.debug(
                "local account '%s' started",
                self.flow_config["username"])
        except flow.Flow.FlowError as start_up_err:
            LOG.debug("start_up failed: '%s'", str(start_up_err))
            # Account doesn't exist locally, try to create the account first
            # This automatically creates a local device
            try:
                self.flow.create_account(
                    self.flow_config["username"],
                    self.flow_config["password"],
                    self.flow_config["server_uri"],
                    self.flow_config["device_name"],
                    "",  # Phone Number
                )
                LOG.info(
                    "account '%s' with device '%s' created",
                    self.flow_config["username"],
                    self.flow_config["device_name"])
            except flow.Flow.FlowError as create_account_err:
                LOG.debug(
                    "create_account failed: '%s'",
                    str(create_account_err))
                # Account exists, create new device
                self.flow.create_device(
                    self.flow_config["username"],
                    self.flow_config["password"],
                    self.flow_config["server_uri"],
                    self.flow_config["device_name"],
                    self.flow_config["platform"],
                    self.flow_config["os_release"])
                LOG.info(
                    "local Device '%s' for '%s' created",
                    self.flow_config["device_name"],
                    self.flow_config["username"])

    def init_http(self):
        """Initializes the HTTPServer instance."""
        self.http_server = http.HTTPServer(self)

    def group_userlist(self):
        """Performs the LDAP account listing on the config provided group."""
        group_dn = self.ldap_config["group_dn"]
        ldap_group = self.ldap_conn.get_group(group_dn)
        users = ldap_group.userlist()
        LOG.debug(users)
        return users

    def write_config(self):
        """Write config for CLI mode to $SEMLDAP_CONFIGDIR."""
        if not common.CONFIG_DIR_ENV_VAR in os.environ:
            LOG.error("env variable '$%s' must be set with "
                      "a config directory (e.g. '~/.config/flow-ldap')",
                      common.CONFIG_DIR_ENV_VAR)
            return False
        config_dir_path = os.environ[common.CONFIG_DIR_ENV_VAR]
        if os.path.exists(config_dir_path):
            if not os.path.isdir(config_dir_path):
                LOG.error("'%s' exists and is not a dir")
                return False
        else:  # does not exist, create it
            os.mkdir(config_dir_path)

        # Save config
        config = RawConfigParser()
        config.add_section(common.FLOW_LDAP_SERVER_CONFIG_SECTION)
        config.set(
            common.FLOW_LDAP_SERVER_CONFIG_SECTION,
            "uri",
            "http://%s:%s/%s" % (
                self.server_config["listen_address"],
                self.server_config["listen_port"],
                common.SERVER_JSON_RPC_URL_PATH))

        config_file_name = os.path.join(
            config_dir_path,
            common.FLOW_LDAP_SERVER_CONFIG_FILE_NAME)
        with open(config_file_name, "wb") as config_file:
            config.write(config_file)

        LOG.info("config file created: '%s'", config_file_name)

        return True

    def run(self):
        """Server main loop.
        It performs the following actions:
            - LDAP periodic poll (on new thread)
            - Flow notification processing (on new thread)
            - CLI HTTP request processing (on main thread)
        """

        if not self.initialized:
            raise Exception("server not initialized, cannot run")

        self.loop_cron.set()
        self.cron_thread.start()

        self.loop_flow.set()
        self.flow_thread.start()

        self.threads_running = True

        # Run HTTP server on main thread
        self.run_http()

    def run_cron(self):
        """Loops the cron schedule."""
        LOG.debug("cron thread started")
        while self.loop_cron.is_set():
            schedule.run_pending()
            time.sleep(0.1)
        LOG.debug("cron thread finished")

    def run_flow(self):
        """Loops Flow notification processing."""
        LOG.debug("flow thread started")
        while self.loop_flow.is_set():
            self.flow.process_one_notification(timeout_secs=0.05)
        LOG.debug("flow thread finished")

    def run_http(self):
        """Runs the HTTP server."""
        LOG.debug("http started")
        self.http_server.run()
        LOG.debug("http finished")

    def cleanup(self):
        """Server cleanup. Must be called before the program exits."""
        LOG.debug('server cleanup')

        if self.threads_running:
            self.loop_cron.clear()
            self.loop_flow.clear()

        if self.flow:
            self.flow.terminate()

    @staticmethod
    def daemonize():
        """Forks the process as daemon process and exits."""
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as os_err:
            LOG.error("Could not start daemon: %s", str(os_err))
            sys.exit(1)
        os.setsid()
        try:
            pid = os.fork()
            if pid > 0:
                LOG.info("Daemon started, pid: %d", pid)
                sys.exit(0)
        except OSError as os_err:
            LOG.error("Could not start daemon: %s", str(os_err))
            sys.exit(1)
        os.chdir("/")
        os.umask(0)
        dev_null = open("/dev/null", "r+")
        os.dup2(dev_null.fileno(), sys.stdout.fileno())
        os.dup2(dev_null.fileno(), sys.stderr.fileno())
        os.dup2(dev_null.fileno(), sys.stdin.fileno())
