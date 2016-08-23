"""
server.py

Server mode source code.
"""

import sys
import os
from ConfigParser import RawConfigParser
import logging
import time

from flow import Flow

import utils
import http
from log import app_log
import db.local_db
import db.backup
import sync.ldap_sync
import cron
import server_config
from ldap_factory import LDAPFactory
from flowpkg import flow_setup, flow_util
from flowpkg.flow_notify import FlowNotify
from flowpkg.handler import (
    LDAPBindRequestHandler,
    ChannelMemberEventHandler,
    UploadHandler,
    TeamMemberEventHandler,
)
from log.flow_log_channel_handler import FlowRemoteLogger


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
        self.config = None
        self.flow = None
        self.flow_remote_logger = None
        self.ldap = None
        self.db = None
        self.cron = None
        self.ldap_sync = None
        self.http_server = None
        self.threads_running = False
        self.flow_notify = None
        self.ldap_bind_request_handler = None
        self.cme_handler = None
        self.upload_handler = None
        self.ldap_factory = None
        self.flow_username = ""
        self.account_id = ""
        self.ldap_team_id = ""
        self.backup_cid = ""
        self.log_cid = ""
        self.config_dir_path = ""
        self.threads_running = False

        if not self.set_config_dir():
            return

        app_log.setup_server_logging(self.debug, self.logging_destination)
        LOG.debug("initializing semaphor-ldap server")
        LOG.debug("config directory: '%s'", self.config_dir_path)

        if not options.config or not os.path.isfile(options.config):
            LOG.error("Missing server *.cfg file, see --help.")
            return

        self.config = server_config.ServerConfig(options.config)

        self.init_flow()
        self.init_flow_log_channel()
        self.init_ldap()
        self.init_cron()
        self.init_db()
        self.init_ldap_sync()
        self.init_config_sync()
        self.init_flow_notify()
        self.init_scan_prescribed_channels()
        self.init_admins_on_channels()
        self.init_notif_handlers()
        self.init_http()

        self.write_auto_connect_config()
        
        self.initialized = True
        LOG.info("server initialized")

        # Commented out for now
        # if sys.platform == "linux2":
        #     LOG.info("going daemon")
        #     self.daemonize()

    def set_config_dir(self):
        """Set semaphor-ldap config directory."""
        self.config_dir_path = utils.get_config_path()
        if os.path.exists(self.config_dir_path):
            if not os.path.isdir(self.config_dir_path):
                LOG.error("'%s' exists and is not a dir")
                return False
        else:  # does not exist, create it
            os.mkdir(self.config_dir_path)
        return True

    def configure_logging(self, destination):
        """Configure logging"""
        self.logging_destination = destination
        app_log.setup_server_logging(self.debug, self.logging_destination)

    def run_backup(self):
        LOG.debug("running db backup")
        db.backup.run(
            self.db,
            self.flow,
            self.ldap_team_id,
            self.backup_cid,
        )

    def set_db_backup_from_config(self):
        minutes = int(self.config.get("db-backup-minutes"))
        self.cron.update_task_frequency(minutes, self.run_backup)

    def schedule_db_back_up(self):
        """Schedules the DB backup process."""
        self.set_db_backup_from_config()
        # Whenever "db-backup-minutes" variable is updated
        # set_db_backup_from_config will be executed
        self.config.register_trigger_for_var(
            "db-backup-minutes",
            self.set_db_backup_from_config,
        )

    def init_db(self):
        """Initializes the db object"""
        LOG.debug("initializing db")
        schema_file_name = self.config.get("local-db-schema")
        local_db_name = utils.local_db_path(
            self.flow_username,
            self.config_dir_path, 
        )
        self.db = db.local_db.LocalDB(
            schema_file_name, 
            local_db_name, 
        )
        self.schedule_db_back_up()

    def init_ldap(self):
        """Initializes LDAP from config values."""
        LOG.debug("initializing ldap")
        self.ldap_factory = LDAPFactory(self.config)
        # Make a dummy connection to test LDAP config
        self.ldap_factory.get_connection()

    def init_cron(self):
        """Initializes the cron process."""
        LOG.debug("initializing cron")
        self.cron = cron.Cron()

    def init_admins_on_channels(self):
        """Performs the following actions:
        1. Add config admins on LDAP team to log channel.
        """
        flow_util.add_admins_to_channel(
            self.flow, 
            self.ldap_team_id,
            self.log_cid,
        )

    def set_ldap_sync_from_config(self):
        """Sets the LDAP sync interval from config value."""
        minutes = int(self.config.get("ldap-sync-minutes"))
        self.cron.update_task_frequency(minutes, self.ldap_sync.run)

    def init_ldap_sync(self):
        """Initializes the ldap sync process and schedules it."""
        LOG.debug("initializing ldap sync scheduling")
        self.ldap_sync = sync.ldap_sync.LDAPSync(self)
        self.set_ldap_sync_from_config()
        # Whenever "ldap-sync-minutes" variable is updated
        # set_ldap_sync_from_config will be executed
        self.config.register_trigger_for_var(
            "ldap-sync-minutes",
            self.set_ldap_sync_from_config,
        )

    def init_config_sync(self):
        """Initializes the config sync process."""
        LOG.debug("initializing sync config")
        self.cron.update_task_frequency(
            utils.SYNC_CONFIG_FREQ_MINUTES, 
            self.config.sync_config,
        )

    def init_flow_notify(self):
        LOG.debug("initializing flow notification system")
        self.flow_notify = FlowNotify(self)

    def init_scan_prescribed_channels(self):
        """Performs a scan over the prescribed channels
        and adds remaining accounts to them.
        """
        LOG.debug("init scan prescribed channels")
        prescribed_channel_ids = flow_util.get_prescribed_cids(
            self.flow, 
            self.ldap_team_id, 
        )
        if prescribed_channel_ids:
            flow_util.rescan_accounts_on_channels(
                self.flow, 
                self.db, 
                self.ldap_team_id,
                prescribed_channel_ids,
            )

    def init_flow(self):
        """Initializes the flow service."""
        LOG.debug("initializing flow")
        try:
            self.flow, setup_data = flow_setup.run(self.config)
            self.account_id = self.flow.account_id()
            self.flow_username = self.flow.identifier()["username"]
            self.ldap_team_id = setup_data["ldap_team_id"]
            self.backup_cid = setup_data["backup_cid"]
            self.log_cid = setup_data["log_cid"]
        except Exception as exception:
            raise SemaphorLDAPServerError(exception)

    def init_flow_log_channel(self):
        """Initializes the logging of errors to a semaphor channel."""
        LOG.debug("initializing error logging to flow channel")
        self.flow_remote_logger = FlowRemoteLogger(self.flow, self.log_cid)        
        app_log.configure_flow_log(self.flow_remote_logger)

    def init_http(self):
        """Initializes the HTTPServer instance."""
        self.http_server = http.HTTPServer(self)

    def init_notif_handlers(self):
        self.ldap_bind_request_handler = LDAPBindRequestHandler(self)
        self.cme_handler = ChannelMemberEventHandler(self)
        self.upload_handler = UploadHandler()
        self.tme_handler = TeamMemberEventHandler(self)
        self.flow_notify.add_handler(self.ldap_bind_request_handler)
        self.flow_notify.add_handler(self.cme_handler)
        self.flow_notify.add_handler(self.upload_handler)
        self.flow_notify.add_handler(self.tme_handler)

    def write_auto_connect_config(self):
        """Write config for CLI mode to the config directory."""
        # Save config
        config = RawConfigParser()
        config.add_section(utils.AUTOCONNECT_CONFIG_SECTION)
        config.set(
            utils.AUTOCONNECT_CONFIG_SECTION,
            "uri",
            "http://%s:%s/%s" % (
                self.config.get("listen-address"),
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
            self.config_dir_path,
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
        if not self.initialized:
            raise SemaphorLDAPServerError("server not initialized, cannot run")

        # Run an initial db sync
        self.ldap_sync.run()

        # Start cron thread, auth listener thread and remote logger thread
        self.cron.start()
        self.flow_notify.start()
        self.flow_remote_logger.start()
        self.threads_running = True

        # Run HTTP server on main thread
        self.run_http()

    def run_http(self):
        """Runs the HTTP server."""
        LOG.debug("http started")
        self.http_server.run()
        LOG.debug("http finished")

    def cleanup(self):
        """Server cleanup. Must be called before the program exits."""
        LOG.debug('server cleanup start')
        if self.threads_running:
            self.cron.stop()
            self.flow_notify.stop()
            self.flow_remote_logger.stop()
            self.cron.join()
            self.flow_notify.join()
            self.flow_remote_logger.join()
        if self.flow:
            self.flow.terminate()
        LOG.debug('server cleanup done')

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
