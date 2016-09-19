"""
server.py

Server mode source code.
"""

import sys
import os
from ConfigParser import RawConfigParser
import logging
import threading
import time

from src import (
    utils,
    app_platform,
    cron,
    server_config,
)
from src.http.http_local_server import HTTPServer
from src.sync import ldap_sync
from src.log import app_log
from src.db import (
    local_db,
)
from src.ldap_factory import LDAPFactory
from src.flowpkg import dma_manager


LOG = logging.getLogger("server")


class SemaphorLDAPServerError(Exception):
    """Exception class used for Server errors."""
    pass


class Server(object):
    """Runs the server mode for this application."""

    def __init__(self, options=None, stop_server_event=None):
        self.config = None
        self.dma_manager = None
        self.db = None
        self.cron = None
        self.ldap_sync = None
        self.http_server = None
        self.threads_running = False
        self.ldap_factory = None
        self.threads_running = False
        self.ldap_sync_on = threading.Event()
        self.stop_server = stop_server_event or threading.Event()

        self.init_config_dir()
        self.init_config(options)
        self.init_log()
        LOG.info("initializing semaphor-ldap server")
        self.init_cron()
        self.init_ldap()
        self.init_db()
        self.init_dma()
        self.init_ldap_sync()
        self.init_http()
        self.write_auto_connect_config()

        LOG.info("server initialized")
        # Commented out for now
        # if sys.platform == "linux2":
        #     LOG.info("going daemon")
        #     self.daemonize()

    def init_config_dir(self):
        """Set semaphor-ldap config directory."""
        config_dir_path = app_platform.get_config_path()
        if os.path.exists(config_dir_path):
            if not os.path.isdir(config_dir_path):
                raise SemaphorLDAPServerError("'%s' exists and is not a dir")
        else:  # does not exist, create it
            os.mkdir(config_dir_path)

    def set_log_dest(self):
        """Updates the server log destination."""
        log_dest = self.config.get("log-dest")
        app_log.set_log_destination(log_dest)

    def set_verbose(self):
        """Updates the server verbose mode."""
        verbose = self.config.get("verbose") == "yes"
        app_log.set_log_debug(verbose)

    def init_log(self):
        """Initialize logging for the server."""
        app_log.setup_server_logging()
        debug = self.config.get("verbose") == "yes" or False
        app_log.set_log_debug(debug)
        config_log_dest = self.config.get("log-dest")
        logging_destination = config_log_dest or \
            app_log.supported_log_destinations()[0]
        app_log.set_log_destination(logging_destination)
        if not config_log_dest:
            self.config.set_key_value("log-dest", logging_destination)
        self.config.register_callback(
            ["log-dest"],
            self.set_log_dest,
        )
        self.config.register_callback(
            ["verbose"],
            self.set_verbose,
        )

    def init_db(self):
        """Initializes the db object"""
        LOG.info("initializing db")
        schema_file_name = self.config.get("local-db-schema") or \
            app_platform.get_default_schema_path()
        self.db = local_db.LocalDB(schema_file_name)

    def init_ldap(self):
        """Initializes LDAP from config values."""
        LOG.info("initializing ldap")
        self.ldap_factory = LDAPFactory(self.config)
        self.config.register_callback(
            server_config.LDAP_VARIABLES,
            self.ldap_factory.reload_config,
        )

    def init_cron(self):
        """Initializes the cron process."""
        LOG.info("initializing cron")
        self.cron = cron.Cron()

    def init_dma(self):
        """Initializes the DMA manager object."""
        self.dma_manager = dma_manager.DMAManager(self)

    def set_ldap_sync_mins_from_config(self):
        """Sets the LDAP sync interval from config value."""
        minutes = int(self.config.get("ldap-sync-minutes"))
        self.cron.update_task_frequency(minutes, self.ldap_sync.run_sync)

    def set_ldap_sync_on_from_config(self):
        """Sets the LDAP sync on/off state from the config."""
        sync_on = self.config.get("ldap-sync-on")
        if sync_on == "yes":
            self.ldap_sync_on.set()
        else:
            self.ldap_sync_on.clear()

    def init_ldap_sync(self):
        """Initializes the ldap sync process and schedules it.
        It also registers the ldap-sync config callbacks."""
        LOG.info("initializing ldap sync scheduling")
        self.ldap_sync = ldap_sync.LDAPSync(self)
        self.config.register_callback(
            ["ldap-sync-minutes"],
            self.set_ldap_sync_mins_from_config,
        )
        self.set_ldap_sync_mins_from_config()
        self.config.register_callback(
            ["ldap-sync-on"],
            self.set_ldap_sync_on_from_config,
        )
        self.set_ldap_sync_on_from_config()

    def init_config(self, options):
        """Initializes the config handler."""
        # If not provided in args, use config from default location
        if options and hasattr(options, "config") and options.config:
            config_file = options.config
        else:
            config_file = app_platform.get_default_server_config()
        # If it doesn't exist, then create it with default values
        if not os.path.isfile(config_file):
            server_config.create_config_file(config_file)
        # Load config file values to memory
        self.config = server_config.ServerConfig(self, config_file)

    def init_http(self):
        """Initializes the HTTPServer instance."""
        self.http_server = HTTPServer(self)

    def write_auto_connect_config(self):
        """Write config for CLI mode to the config directory."""
        # Save config
        config = RawConfigParser()
        config.add_section(utils.AUTOCONNECT_CONFIG_SECTION)
        config.set(
            utils.AUTOCONNECT_CONFIG_SECTION,
            "uri",
            "http://%s:%s/%s" % (
                utils.LOCAL_SERVER_HOST,
                self.config.get("listen-port"),
                utils.SERVER_JSON_RPC_URL_PATH,
            ),
        )
        config.set(
            utils.AUTOCONNECT_CONFIG_SECTION,
            "auth-token",
            self.http_server.auth_token,
        )
        config_file_name = os.path.join(
            app_platform.get_config_path(),
            utils.AUTOCONNECT_CONFIG_FILE_NAME,
        )
        with open(config_file_name, "wb") as config_file:
            config.write(config_file)
        LOG.info("config file created: '%s'", config_file_name)

    def run(self):
        """Server main loop.
        It performs the following actions:
            - Starts the LDAP sync thread
            - Starts the Bind Request Handler thread.
            - Starts the CLI HTTP request processing (on main thread)
        """
        # Start cron thread, auth listener thread and remote logger thread
        self.cron.start()
        self.dma_manager.start()
        self.http_server.start()
        self.threads_running = True

        # Run server termination check on main thread
        self.wait_finish()

    def wait_finish(self):
        """Main thread will loop until the stop_server event is set."""
        while not self.stop_server.is_set():
            time.sleep(0.25)

    def cleanup(self):
        """Server cleanup. Must be called before the program exits."""
        LOG.info("server cleanup start")
        if self.threads_running:
            self.cron.stop()
            self.cron.join()
            self.dma_manager.stop()
            self.http_server.stop()
            self.http_server.join()
        self.config.store_config()
        LOG.info("server cleanup done")

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
