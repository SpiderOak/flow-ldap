"""
app_platform.py

Platform specific definitions.

If $APPDATA is the Application data directory for semaphor-ldap,
then here's the directory structure:
$APPDATA/resources/app/img/bot.jpg
$APPDATA/resources/app/schema/dma.sql
$APPDATA/resources/app/backend/schema/per_local_account.sql
$APPDATA/resources/app/backend/schema/per_local_account_and_channel.sql
$APPDATA/resources/app/backend/semaphor-backend

If $CONFIG is the Configuration data directory for semaphor-ldap,
then here's the directory structure:
$CONFIG/server-config.cfg
$CONFIG/*.sqlite  # semaphor local DBs
$CONFIG/DMA*.sqlite  # DMA local DB
$CONFIG/semaphor_backend_*.log
$CONFIG/semaphor_ldap_*.log
$CONFIG/server-auto-connect.log
"""

import sys
import os
import time

from src import utils


_DEFAULT_APP_OSX_PATH = "/Applications/Semaphor LDAP.app/Contents/Resources/app"
_DEFAULT_APP_LINUX_RPM_PATH = "/opt/semaphor-ldap-linux-x64/resources/app"
_DEFAULT_APP_LINUX_DEB_PATH = "/usr/share/semaphor-ldap/resources/app"
_DEFAULT_APP_WINDOWS_PATH = r"semaphor-ldap\resources\app"

_DEFAULT_CONFIG_DIR = "semaphor-ldap"
_DEFAULT_ATTACHMENT_DIR = "downloads"
_DEFAULT_BACKEND_DIR = "backend"
_DEFAULT_SCHEMA_DIR = "schema"
_EXE_EXT = (".exe" if sys.platform == "win32" else "")
_DEFAULT_FLOWAPPGLUE_BINARY_DEV_NAME = "flowappglue%s" % _EXE_EXT
_DEFAULT_FLOWAPPGLUE_BINARY_PROD_NAME = "semaphor-backend%s" % _EXE_EXT

SEMLDAP_CONFIGDIR_ENV_VAR = "SEMLDAP_CONFIGDIR"

def _osx_app_path():
    """Returns the default application directory for OSX."""
    return _DEFAULT_APP_OSX_PATH


def _linux_app_path():
    """Returns the default application directory for Linux
    depending on the packaging (deb or rpm).
    """
    # check if RPM first
    if os.path.exists(_DEFAULT_APP_LINUX_RPM_PATH):
        return _DEFAULT_APP_LINUX_RPM_PATH
    # otherwise return DEB
    return _DEFAULT_APP_LINUX_DEB_PATH


def _windows_app_path():
    """Returns the default application directory for Windows."""
    return os.path.join(os.environ["ProgramFiles"],
                        _DEFAULT_APP_WINDOWS_PATH)


_APP_OS_PATH_MAP = {
    "darwin": _osx_app_path,
    "linux2": _linux_app_path,
    "win32": _windows_app_path,
}


def get_default_backend_path():
    """Returns the default schema directory depending on the platform.
    E.g. on OSX it would be:
    /Applications/Semaphor.app/Contents/Resources/app/schema.
    """
    return os.path.join(
        _APP_OS_PATH_MAP[sys.platform](), 
        _DEFAULT_BACKEND_DIR,
    )


def get_default_backend_schema_path():
    """Returns the default schema directory depending on the platform.
    E.g. on OSX it would be:
    /Applications/Semaphor.app/Contents/Resources/app/schema.
    """
    return os.path.join(
        get_default_backend_path(),
        _DEFAULT_SCHEMA_DIR,
    )


def get_default_schema_path():
    return os.path.join(
        _APP_OS_PATH_MAP[sys.platform](),
        _DEFAULT_SCHEMA_DIR,
	"dma.sql",
    )


def get_default_img_path():
    return os.path.join(
        _APP_OS_PATH_MAP[sys.platform](),
	"img",
    )


def get_config_path():
    """Returns the default semaphor-ldap config path."""
    CONFIG_OS_PATH_MAP = {
        "darwin": "Library/Application Support",
        "linux2": ".config",
        "win32": r"%LOCALAPPDATA%",
    }
    if SEMLDAP_CONFIGDIR_ENV_VAR in os.environ:
        return os.environ[SEMLDAP_CONFIGDIR_ENV_VAR]
    config_path = CONFIG_OS_PATH_MAP[sys.platform]
    if sys.platform in ["linux2", "win32"]:
        config_path = os.path.join(
            os.path.expanduser("~"),
            config_path,
        )
    return os.path.join(
        config_path,
        _DEFAULT_CONFIG_DIR,
    )


def get_default_attachment_path():
    """Returns the default attachment directory depending on the platform.
    E.g. on OSX it would be:
    $HOME/Library/Application Support/semaphor/downloads.
    """
    return os.path.join(
        get_config_path(), 
        _DEFAULT_ATTACHMENT_DIR,
    )


def get_default_flowappglue_path():
    """Returns a string with the absolute path for
    the flowappglue binary; the return value depends on the platform.
    """
    flowappglue_path = os.path.join(
        get_default_backend_path(),
        _DEFAULT_FLOWAPPGLUE_BINARY_PROD_NAME,
    )
    if os.path.isfile(flowappglue_path):
        return flowappglue_path
    flowappglue_path = os.path.join(
        get_default_backend_path(),
        _DEFAULT_FLOWAPPGLUE_BINARY_DEV_NAME,
    )
    return flowappglue_path


def get_glue_out_filename():
    """Returns a string with a default filename for the
    flowappglue output log file.
    Default Format: "semaphor_backend_%Y%m%d%H%M%S.log".
    """
    return os.path.join(
        get_config_path(),
        time.strftime("semaphor_backend_%Y%m%d%H%M%S.log")
    )


def get_default_server_config():
    """Returns the default server config file for the platform."""
    return os.path.join(
        get_config_path(),
        utils.SERVER_CONFIG_FILE_NAME,
    )


def local_db_path(username, config_dir_path=get_config_path()):
    """Returns the local DB filename for the DMA account."""
    return os.path.join(
        get_config_path(),
        "%s.sqlite" % username,
    )
