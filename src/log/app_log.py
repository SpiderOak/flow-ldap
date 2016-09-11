"""
app_log.py

Log configuration for the semaphor-ldap application.
"""

import sys
import os
import time
import threading
import logging
import logging.handlers

from src import app_platform
from src.log import console_handler
from src.log.flow_log_channel_handler import FlowLogChannelHandler


ROOT_LOGGER = logging.getLogger("")
LOG_LOCK = threading.Lock()
PLATFORM_HANDLERS = {}


def supported_log_destinations():
    """Returns a list with the supported logging
    destinations for the platform.
    """
    if sys.platform == "linux2":
        return ["syslog", "file"]
    elif sys.platform == "darwin":
        return ["file"]
    elif sys.platform == "win32":
        return ["event", "file"]
    return []


def configured_syslog_handler():
    """Configures the builtin logging 'SysLogHandler' for Linux."""
    syslog_handler = logging.handlers.SysLogHandler("/dev/log")
    syslog_formatter = logging.Formatter(
        "%(app_name)s[%(process)d]: %(name)s %(levelname)s %(message)s",
    )
    syslog_handler.setFormatter(syslog_formatter)

    class AppFilter(logging.Filter):
        """Needed to log the application log on syslog entries.
        '%(processName)' shows 'MainProcess' instead of the python app.
        """

        def filter(self, record):
            record.app_name = 'semaphor-ldap'
            return True
    syslog_handler.addFilter(AppFilter())
    return syslog_handler


def configured_eventlog_handler():
    """Configures the builtin logging 'NTEventLogHandler' for Windows."""
    dllname = os.path.join(
        os.path.dirname(sys.executable),
        "win32service.pyd",
    )
    event_handler = logging.handlers.NTEventLogHandler(
        appname="Semaphor-LDAP-Server-Process",
        dllname=dllname,
    )
    event_handler_formatter = logging.Formatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    event_handler.setFormatter(event_handler_formatter)
    return event_handler


def configured_file_handler():
    """Configures the builtin logging 'FileHandler'."""
    config_dir_path = app_platform.get_config_path()
    log_file_name = os.path.join(
        config_dir_path,
        time.strftime("semaphor_ldap_%Y%m%d-%H%M%S.log"),
    )
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_name,
        maxBytes=40 * 1024 * 1024,  # 40 MB
        backupCount=5,  # up to 5 rollover files
    )
    file_handler_formatter = logging.Formatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    file_handler.setFormatter(file_handler_formatter)
    return file_handler


def configured_console_handler(detailed=True):
    """Configure the 'ConsoleHandler' for logging to console.
    See 'console_handler.py'.
    """
    _console_handler = console_handler.ConsoleHandler()
    console_formatter = logging.Formatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s"
        if detailed else "%(message)s"
    )
    _console_handler.setFormatter(console_formatter)
    return _console_handler


def setup_common_logging():
    """Setup common logging configuration for the application."""
    # Do not show 'requests' lib INFO logs
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_platform_handlers():
    """Returns the supported log handlers for the platform."""
    supported = supported_log_destinations()
    handlers = {}
    for log_type in supported:
        if log_type == "syslog":
            handlers["syslog"] = configured_syslog_handler()
        elif log_type == "event":
            handlers["event"] = configured_eventlog_handler()
        elif log_type == "file":
            handlers["file"] = configured_file_handler()
    return handlers


def setup_server_logging():
    """Setups the logging configuration for the server mode."""
    setup_common_logging()
    PLATFORM_HANDLERS.update(get_platform_handlers())


def set_log_debug(enable=True):
    """Setups the verbose mode of the logging configuration."""
    ROOT_LOGGER.setLevel(logging.DEBUG if enable else logging.INFO)


def set_log_destination(destination):
    """Setup logging configuration for the Server mode."""
    LOG_LOCK.acquire()
    try:
        # Add handler only if supported on platform
        if destination in PLATFORM_HANDLERS:
            # Check if already configured
            if PLATFORM_HANDLERS[destination] not in ROOT_LOGGER.handlers:
                for _, plat_handler in PLATFORM_HANDLERS.items():
                    if plat_handler in ROOT_LOGGER.handlers:
                        ROOT_LOGGER.removeHandler(plat_handler)
                ROOT_LOGGER.addHandler(PLATFORM_HANDLERS[destination])
    finally:
        LOG_LOCK.release()


def setup_cli_logging(debug):
    """Setups logging configuration for the CLI mode."""
    setup_common_logging()
    set_log_debug(debug)
    _console_handler = configured_console_handler(detailed=False)
    ROOT_LOGGER.addHandler(_console_handler)


def configure_flow_log(flow_remote_logger):
    """Configures logging to log ERRORs to the LOG channel
    using the flow_remote_logger.
    """
    flow_log_handler = FlowLogChannelHandler(flow_remote_logger)

    class OnlyError(logging.Filter):

        def filter(self, record):
            return record.levelno == logging.ERROR

    class NotFlow(logging.Filter):

        def filter(self, record):
            return record.name != "flow"
    flow_log_handler.addFilter(OnlyError())
    flow_log_handler.addFilter(NotFlow())
    channel_formatter = logging.Formatter(
        "%(asctime)s %(name)s %(message)s",
    )
    flow_log_handler.setFormatter(channel_formatter)
    ROOT_LOGGER.addHandler(flow_log_handler)
