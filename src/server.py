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

from flow import Flow
import ldap_reader
from . import (
    common,
    http,
    app_log,
)


SERVER_CONFIG = "Server"
LDAP_MAIN_CONFIG_SECTION = "LDAP"
LDAP_VENDOR_CONFIG_SECTION = "LDAP Vendor"
SEMAPHOR_CONFIG_SECTION = "Semaphor"

LOG = logging.getLogger("server")


class SemaphorLDAPServerError(Exception):
    """Exception class used for Server errors."""
    pass


class Server(object):
    """Runs the server mode for this application."""

    def __init__(self, options):
        self.debug = options.debug
        self.logging_destination = options.log_dest
        self.initialized = False
        self.flow = None
        self.ldap_conn = None
        self.http_server = None
        self.server_config = {}  # config_var -> config_value
        self.ldap_config = {}  # config_var -> config_value
        self.ldap_vendor_config = {}  # config_var -> config_value
        self.flow_config = {}  # config_var -> config_value
        self.threads_running = False

        app_log.setup_server_logging(self.debug, self.logging_destination)
        LOG.debug("initializing semaphor-ldap server")

        if not options.config or not os.path.isfile(options.config):
            LOG.error("Missing server *.cfg file, see --help.")
            return

        self.read_config(options.config)

        self.init_ldap()

        try:
            self.init_flow()
        except Flow.FlowError as flow_err:
            if self.flow:
                self.flow.terminate()
            LOG.error("Semaphor init: %s", flow_err)
            return

        self.init_cron()

        self.init_http()

        self.cron_thread = threading.Thread(target=self.run_cron, args=())
        self.loop_cron = threading.Event()
        self.flow_thread = threading.Thread(target=self.run_flow, args=())
        self.loop_flow = threading.Event()
        self.threads_running = False

        config_written = self.write_auto_connect_config()
        if config_written:
            self.initialized = True

        LOG.info("server initialized")

        # Commented out for now
        # if sys.platform == "linux2":
        #     LOG.info("going daemon")
        #     self.daemonize()

    def configure_logging(self, destination):
        """Configure logging"""
        self.logging_destination = destination
        app_log.setup_server_logging(self.debug, self.logging_destination)

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
            SEMAPHOR_CONFIG_SECTION]
        self.server_config = config_dict[
            SERVER_CONFIG]

    def init_cron(self):
        """Initializes the cron configuration for this application."""
        LOG.debug("initializing cron")
        minutes = int(self.ldap_config["poll_group_minutes"])
        schedule.every(minutes).minutes.do(self.group_userlist)

    def init_ldap(self):
        """Initializes LDAP from config values."""
        LOG.debug("initializing ldap")
        self.ldap_conn = ldap_reader.LdapConnection(
            self.ldap_config["uri"],
            self.ldap_config["base_dn"],
            self.ldap_config["admin_user"],
            self.ldap_config["admin_pw"],
            self.ldap_vendor_config)

    def init_flow(self):
        """Initializes Flow instance from config info.
        - If the account and device already exist, it will use them.
        - If the account exists, but there's no device, it creates a device.
        - If the account does not exist, it creates the account + a device.
        """
        LOG.debug("initializing flow")
        flowappglue = self.flow_config["flowappglue"] \
            if "flowappglue" in self.flow_config else ""
        schema_dir = self.flow_config["schema_dir"] \
            if "schema_dir" in self.flow_config else ""
        self.flow = Flow(
            flowappglue=flowappglue,
            schema_dir=schema_dir,
            host=self.flow_config["flow_service_host"],
            port=self.flow_config["flow_service_port"],
            use_tls=self.flow_config["flow_service_use_tls"],
            server_uri=self.flow_config["server_uri"],
        )

        # An Account + Device may already be local
        # Try to start up first
        try:
            self.flow.start_up(
                username=self.flow_config["username"],
            )
            LOG.debug(
                "local account '%s' started",
                self.flow_config["username"])
            return
        except Flow.FlowError as start_up_err:
            LOG.debug("start_up failed: '%s'", str(start_up_err))

        # TODO: use create_dm_device() when available
        # Account may already exist, but not locally.
        # Try to create new device
        try:
            self.flow.create_device(
                username=self.flow_config["username"],
                password=self.flow_config["password"],
            )
            LOG.info(
                "local Device '%s' for '%s' created",
                self.flow_config["device_name"],
                self.flow_config["username"])
            return
        except Flow.FlowError as create_device_err:
            LOG.debug(
                "create_device failed: '%s'",
                str(create_device_err))

        # Account may not exist.
        # Try to create Account + Device
        # for the Directory Management Account
        self.flow.create_dm_account(
            username=self.flow_config["username"],
            password=self.flow_config["password"],
            dmk=self.flow_config["directory_management_key"],
        )
        LOG.info(
            "account '%s' with device '%s' created",
            self.flow_config["username"],
            self.flow_config["device_name"])

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

    def write_auto_connect_config(self):
        """Write config for CLI mode to $SEMLDAP_CONFIGDIR."""
        if common.CONFIG_DIR_ENV_VAR not in os.environ:
            LOG.error("env variable '$%s' must be set with "
                      "a config directory (e.g. '~/.config/semaphor-ldap')",
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
        config.add_section(common.AUTOCONNECT_CONFIG_SECTION)
        config.set(
            common.AUTOCONNECT_CONFIG_SECTION,
            "uri",
            "http://%s:%s/%s" % (
                self.server_config["listen_address"],
                self.server_config["listen_port"],
                common.SERVER_JSON_RPC_URL_PATH))

        config_file_name = os.path.join(
            config_dir_path,
            common.AUTOCONNECT_CONFIG_FILE_NAME)
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
            raise SemaphorLDAPServerError("server not initialized, cannot run")

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
