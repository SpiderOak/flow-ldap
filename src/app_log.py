"""
app_log.py

Log configuration for the semaphor-ldap application.
"""

import sys
import os
import time
import logging
import logging.handlers

import common
import console_handler


def default_log_destination():
    """Returns the default logging destination for the platform."""
    if sys.platform == "linux2":
        return ["syslog", "file"]
    elif sys.platform == "win32":
        return ["event", "file"]
    else:
        return ["file"]


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
    if common.CONFIG_DIR_ENV_VAR not in os.environ:
        print(
            "Error: $%s environment variable must be set." %
            common.CONFIG_DIR_ENV_VAR
        )
        sys.exit(os.EX_USAGE)

    log_file_name = os.path.join(
        os.environ[common.CONFIG_DIR_ENV_VAR],
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

    logging_handler = logging.NullHandler()
    if sys.platform == "linux2" and destination == "syslog":
        logging_handler = configured_syslog_handler()
    elif sys.platform == "win32" and destination == "event":
        logging_handler = configured_eventlog_handler()
    elif destination == "file":
        logging_handler = configured_file_handler()

    logging.getLogger("").addHandler(logging_handler)

    _console_handler = configured_console_handler()
    logging.getLogger("").addHandler(_console_handler)


def setup_cli_logging(debug):
    """Setup logging configuration for the CLI mode."""
    setup_common_logging(debug)
    _console_handler = configured_console_handler(detailed=False)
    logging.getLogger("").addHandler(_console_handler)
