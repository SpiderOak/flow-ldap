"""
utils.py

Utilities and definitions for semaphor-ldap
"""

VERSION = "1.0.1"

AUTOCONNECT_CONFIG_FILE_NAME = "server-auto-connect.cfg"
SERVER_CONFIG_FILE_NAME = "server-config.cfg"
AUTOCONNECT_CONFIG_SECTION = "Semaphor LDAP Server"
SERVER_CONFIG_SECTION = AUTOCONNECT_CONFIG_SECTION
LOCAL_SERVER_HOST = "127.0.0.1"
SERVER_JSON_RPC_URL_PATH = "rpc"

DMA_BACKUP_CHANNEL_SUFFIX_NAME = "-Backup"
DMA_LOG_CHANNEL_SUFFIX_NAME = "-Log"
DMA_TEST_CHANNEL_SUFFIX_NAME = "-Test"

DEFAULT_FLOW_SERVICE_HOST = "flow.spideroak.com"
DEFAULT_FLOW_SERVICE_PORT = "443"
DEFAULT_FLOW_SERVICE_USE_TLS = "true"

FLOW_API_TIMEOUT = 15

URI_FINGERPRINT = "semaphor://enterprise-sign-in/%(fp)s"


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
