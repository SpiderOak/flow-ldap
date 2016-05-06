"""
common.py

Common definitions
"""

VERSION = "0.1"
CONFIG_DIR_ENV_VAR = "SEMLDAP_CONFIGDIR"
AUTOCONNECT_CONFIG_FILE_NAME = "server-auto-connect.cfg"
AUTOCONNECT_CONFIG_SECTION = "Semaphor LDAP Server"
SERVER_JSON_RPC_URL_PATH = "rpc"


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
