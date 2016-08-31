"""
app_log.py

Log configuration for the semaphor-ldap application.
"""

import sys
import os
import time
import logging
import logging.handlers

import src.app_platform
import console_handler
from flow_log_channel_handler import FlowLogChannelHandler


def supported_log_destinations():
    """Returns a list with the supported logging
    destinations for the platform.
    """
    if sys.platform in ["linux2", "darwin"]:
        return ["syslog", "file"]
    elif sys.platform == "win32":
        return ["file", "event"]  # TODO swap
    return []


def configured_syslog_handler():
    """Configures the builtin logging 'SysLogHandler' for Linux."""
    syslog_handler = logging.handlers.SysLogHandler("/dev/log")
    syslog_formatter = logging.Formatter(
        "%(app_name)s[%(process)d]: %(name)s %(levelname)s %(message)s"
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
    return logging.NullHandler()


def configured_file_handler():
    """Configures the builtin logging 'FileHandler'."""
    config_dir_path = src.app_platform.get_config_path()
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
        "%(asctime)s %(name)s %(levelname)s %(message)s"
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


def setup_common_logging(debug):
    """Setup common logging configuration for the application."""
    # Do not show 'requests' lib INFO logs
    logging.getLogger("requests").setLevel(logging.WARNING)
    # Configure flow-python log output
    logging.getLogger("").setLevel(logging.DEBUG if debug else logging.INFO)


def setup_server_logging(debug, destination):
    """Setup logging configuration for the Server mode."""
    setup_common_logging(debug)

    if sys.platform == "linux2" and destination == "syslog":
        logging_handler = configured_syslog_handler()
    elif sys.platform == "win32" and destination == "event":
        logging_handler = configured_eventlog_handler()
    elif destination == "file":
        logging_handler = configured_file_handler()
    else:
        logging_handler = logging.NullHandler()

    logging.getLogger("").addHandler(logging_handler)

    # We log to stdout too
    _console_handler = configured_console_handler()
    logging.getLogger("").addHandler(_console_handler)


def setup_cli_logging(debug):
    """Setup logging configuration for the CLI mode."""
    setup_common_logging(debug)
    _console_handler = configured_console_handler(detailed=False)
    logging.getLogger("").addHandler(_console_handler)


def configure_flow_log(flow_remote_logger):
    """Configure logging errors into the log channel."""
    flow_log_handler = FlowLogChannelHandler(flow_remote_logger)

    class OnlyError(logging.Filter):

        def filter(self, record):
            return record.levelname == logging.ERROR

    class NotFlow(logging.Filter):

        def filter(self, record):
            return record.name != "flow"
    flow_log_handler.addFilter(OnlyError())
    flow_log_handler.addFilter(NotFlow())
    channel_formatter = logging.Formatter(
        "%(asctime)s %(name)s %(message)s",
    )
    flow_log_handler.setFormatter(channel_formatter)
    logging.getLogger("").addHandler(flow_log_handler)
