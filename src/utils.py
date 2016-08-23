"""
utils.py

Utilities and definitions for semaphor-ldap
"""

import sys
import os


# Global variables definition
VERSION = "0.1"
AUTOCONNECT_CONFIG_FILE_NAME = "server-auto-connect.cfg"
AUTOCONNECT_CONFIG_SECTION = "Semaphor LDAP Server"
SERVER_JSON_RPC_URL_PATH = "rpc"
SYNC_CONFIG_FREQ_MINUTES = 1
SEMLDAP_CONFIGDIR_ENV_VAR = "SEMLDAP_CONFIGDIR"
DMA_BACKUP_CHANNEL_SUFFIX_NAME = "-Backup"
DMA_LOG_CHANNEL_SUFFIX_NAME = "-Log"


def raw_config_as_dict(config):
    """Returns a RawConfigParser as a 'dict'.
    Arguments:
    config : RawConfigParser instance.
    E.g. for the following config:
    [Section1]
    var1 = value1
    var2 = value2
    [Section2]
    var3 = value3
    raw_config_as_dict returns:
    {
        "Section1": {
            "var1": "value1",
            "var2": "value2",
        },
        "Section2": {
            "var3": "value3",
        },
    }
    """
    as_dict = {s: dict(config.items(s))
               for s in config.sections()}
    return as_dict


# OS specifics defaults
_CONFIG_OS_PATH_MAP = {
    "darwin": "Library/Application Support/semaphor-ldap",
    "linux2": ".config/semaphor-ldap",
    "win32": r"AppData\Local\semaphor-ldap",
}


def _get_home_directory():
    """Returns a string with the home directory of the current user.
    Returns $HOME for Linux/OSX and %USERPROFILE% for Windows.
    """
    return os.path.expanduser("~")


def get_config_path():
    """Returns the default semaphor-ldap config path."""
    if SEMLDAP_CONFIGDIR_ENV_VAR in os.environ:
        return os.environ[SEMLDAP_CONFIGDIR_ENV_VAR]
    return os.path.join(
        _get_home_directory(),
        _CONFIG_OS_PATH_MAP[sys.platform],
    )


def local_db_path(username, config_dir_path=get_config_path()):
    """Returns the local DB filename for the DMA account."""
    return os.path.join(
        get_config_path(),
        "%s.sqlite" % username,
    )
