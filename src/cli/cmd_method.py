"""
cmd_method.py

Command line method classes.
"""

import string
import getpass

from flow import Flow

from src import utils


class CmdMethod(object):

    @classmethod
    def method(cls):
        class_name = cls.__name__
        name = ""
        for i, char in enumerate(class_name):
            if i != 0 and char in string.ascii_uppercase:
                name += "-"
            name += char
        return name.lower()

    @staticmethod
    def request(args_dict):
        return args_dict

    @staticmethod
    def error(error_dict):
        error_str = "Server Error"
        if "message" in error_dict:
            error_str = error_dict["message"]
            if "data" in error_dict:
                error_str = error_dict["data"]
                if "message" in error_dict["data"]:
                    error_str = error_dict["data"]["message"]
        print("ERROR: %s" % error_str)

    @staticmethod
    def result(result_dict):
        pass

    def response(self, response_dict):
        if "error" in response_dict:
            self.error(response_dict["error"])
        elif "result" in response_dict:
            self.result(response_dict["result"])


class CheckStatus(CmdMethod):

    @staticmethod
    def request(args_dict):
        print("Checking Semaphor-LDAP server status...")
        return args_dict

    @staticmethod
    def result(result_dict):
        print("Server status:\n"
              "- db = %s\n- flow = %s\n- ldap = %s\n- sync = %s" % (
                  result_dict["db"],
                  result_dict["flow"],
                  result_dict["ldap"],
                  result_dict["sync"],
              )
              )


class CreateAccount(CmdMethod):

    @staticmethod
    def request(args_dict):
        print("Creating Directory Management Account...")
        return args_dict

    @staticmethod
    def result(result_dict):
        print("The DMA account was created, "
              "please securely store the following credentials:\n"
              "- Username = %s\n- Recovery Key = %s\n"
              "A Team Join Request was sent to the LDAP Team = %s.\n"
              "To finish the setup please accept the "
              "request and make the DMA an admin." % (
                  result_dict["username"],
                  result_dict["password"],
                  result_dict["orgId"],
              )
              )


class CreateDevice(CmdMethod):

    @staticmethod
    def request(args_dict):
        print("Creating device for account '%s'..." % args_dict["username"])
        return args_dict


class ConfigSet(CmdMethod):

    @staticmethod
    def request(args_dict):
        if "value" in args_dict and args_dict["value"]:
            print("Setting config '%s'..." % args_dict["key"])
        else:  # Prompt variable
            if args_dict.get("key") == "admin-pw":
                args_dict["value"] = getpass.getpass("Password: ")
            else:
                args_dict["value"] = raw_input("Value: ")
        return args_dict


class ConfigList(CmdMethod):

    @staticmethod
    def request(args_dict):
        print("Getting config list...")
        return args_dict

    @staticmethod
    def result(result_dict):
        for group, variables in result_dict.items():
            print("== %s ==" % group)
            for key, value in variables.items():
                if key == "admin-pw":
                    value = "*" * len(value)
                print("  - %s = %s" % (key, value))


class DmaFingerprint(CmdMethod):

    @staticmethod
    def request(args_dict):
        print("Getting Directory Management Account fingerprint...")
        return args_dict

    @staticmethod
    def result(result_dict):
        print("Fingerprint = %s" % result_dict)
        print("URI = %s" % (utils.URI_FINGERPRINT % {"fp": result_dict}))


class GroupUserlist(CmdMethod):

    @staticmethod
    def request(args_dict):
        print("Getting list of accounts from the configured LDAP group...")
        return args_dict

    @staticmethod
    def result(result_dict):
        users = sorted(result_dict, key=lambda k: k["email"])
        for user in users:
            print(
                "%s, uid = %s, ldap-state = %s" % (
                    user["email"],
                    user["uniqueid"],
                    "enabled" if user["enabled"] else "disabled",
                )
            )


class LogDest(CmdMethod):

    @staticmethod
    def request(args_dict):
        print("Setting log destination to %s..." % args_dict["target"])
        return args_dict


class DbUserlist(CmdMethod):

    @staticmethod
    def request(args_dict):
        print("Retrieving users from the local database...")
        return args_dict

    @staticmethod
    def result(result_dict):
        users = sorted(result_dict, key=lambda k: k["email"])
        if not users:
            print("The local DB is currently empty.")
            return
        for user in users:
            # TODO: put in function
            print(
                "%s, uid = %s, ldap-state = %s, "
                "semaphor-guid = %s, semaphor-lock-state = %s" % (
                    user["email"],
                    user["uniqueid"],
                    "enabled" if user["enabled"] else "disabled",
                    user["semaphor_guid"] or "N/A",
                    "unlocked" if user["lock_state"] == Flow.UNLOCK else (
                        "ldap-locked"
                        if user["lock_state"] == Flow.LDAP_LOCK else "full-locked"
                    ),
                )
            )


class LdapSyncTrigger(CmdMethod):

    @staticmethod
    def request(args_dict):
        print("Triggering an LDAP sync...")
        return args_dict


class ServerVersion(CmdMethod):

    @staticmethod
    def result(result_dict):
        print("The server version is: '%s'" % result_dict)


METHOD_CLASSES = {
    MethodClass.method(): MethodClass
    for MethodClass in CmdMethod.__subclasses__()
}


def get_cmd_method(method):
    return METHOD_CLASSES.get(method, CmdMethod)()
