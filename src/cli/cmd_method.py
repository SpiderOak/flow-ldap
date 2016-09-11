"""
cmd_method.py

Command line method classes.
"""

import string
import getpass

from flow import Flow

from src import utils


class CmdMethod(object):
    """'CmdMethod' is the abstract command line method class,
    all command line methods inherit from it and implement their
    request() and result() methods.
    The request() method is used to preprocess command line
    arguments before sending to the server, and possibly
    print something to stdout before the actual request.
    The result() method is used to parse the response from
    the server and show results to stdout
    (currently via simple 'print()'s)
    """

    @classmethod
    def method(cls):
        """Return the method name from the class name.
        If the class name is 'ConfigSet', then the returned
        string is 'config-set'.
        It is used to match the class with the corresponding
        command line client method.
        """
        class_name = cls.__name__
        name = ""
        for i, char in enumerate(class_name):
            if i != 0 and char in string.ascii_uppercase:
                name += "-"
            name += char
        return name.lower()

    def request(self, args_dict):
        """Preprocess the dict args_dict. And returns the
        modified version to send to the server.
        """
        return args_dict

    def error(self, error_dict):
        """Parses the error server response and prints it
        to stdout.
        """
        error_str = "Server Error"
        if "message" in error_dict:
            error_str = error_dict["message"]
            if "data" in error_dict:
                error_str = error_dict["data"]
                if "message" in error_dict["data"]:
                    error_str = error_dict["data"]["message"]
        print("ERROR: %s" % error_str)

    def result(self, result_dict):
        """'result_dict' contains the server response arguments.
        CmdMethods can use this to print the response to stdout.
        """
        pass

    def response(self, response_dict):
        """Parses the JSON-RPC response."""
        if "error" in response_dict:
            self.error(response_dict["error"])
        elif "result" in response_dict:
            self.result(response_dict["result"])


class CheckStatus(CmdMethod):

    def request(self, args_dict):
        print("Checking Semaphor-LDAP server status...")
        return args_dict

    def result(self, result_dict):
        print("Server status:\n"
              "- db = %s\n- flow = %s\n- ldap = %s\n- sync = %s" % (
                  result_dict["db"],
                  result_dict["flow"],
                  result_dict["ldap"],
                  result_dict["sync"],
              )
              )


class CreateAccount(CmdMethod):

    def request(self, args_dict):
        print("Creating Directory Management Account...")
        return args_dict

    def result(self, result_dict):
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

    def request(self, args_dict):
        print("Creating device for account '%s'..." % args_dict["username"])
        return args_dict


class ConfigSet(CmdMethod):

    def request(self, args_dict):
        if "value" not in args_dict or not args_dict["value"]:
            # Prompt variable
            if args_dict.get("key") == "admin-pw":
                args_dict["value"] = getpass.getpass("Password: ")
            else:
                args_dict["value"] = raw_input("Value: ")
        print("Setting config '%s'..." % args_dict["key"])
        return args_dict


class ConfigList(CmdMethod):

    def request(self, args_dict):
        print("Getting config list...")
        return args_dict

    def result(self, result_dict):
        for group, variables in result_dict.items():
            print("== %s ==" % group)
            for key, value in variables.items():
                if key == "admin-pw":
                    value = "*" * len(value)
                print("  - %s = %s" % (key, value))


class DmaFingerprint(CmdMethod):

    def request(self, args_dict):
        print("Getting Directory Management Account fingerprint...")
        return args_dict

    def result(self, result_dict):
        print("Fingerprint = %s" % result_dict)
        print("URI = %s" % (utils.URI_FINGERPRINT % {"fp": result_dict}))


class GroupUserlist(CmdMethod):

    def request(self, args_dict):
        print("Getting list of accounts from the configured LDAP group...")
        return args_dict

    def print_user(self, user):
        print(
            "%s, uid = %s, ldap-state = %s" % (
                user["email"],
                user["uniqueid"],
                "enabled" if user["enabled"] else "disabled",
            )
        )

    def result(self, result_dict):
        users = sorted(result_dict, key=lambda k: k["email"])
        for user in users:
            self.print_user(user)


class LogDest(CmdMethod):

    def request(self, args_dict):
        print("Setting log destination to %s..." % args_dict["target"])
        return args_dict


class DbUserlist(CmdMethod):

    def request(self, args_dict):
        print("Retrieving users from the local database...")
        return args_dict

    def print_user(self, user):
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

    def result(self, result_dict):
        users = sorted(result_dict, key=lambda k: k["email"])
        if not users:
            print("The local DB is currently empty.")
            return
        for user in users:
            self.print_user(user)


class LdapSyncTrigger(CmdMethod):

    def request(self, args_dict):
        print("Triggering an LDAP sync...")
        return args_dict


class ServerVersion(CmdMethod):

    def result(self, result_dict):
        print("The server version is: '%s'" % result_dict)


# CmdMethod class map
METHOD_CLASSES = {
    MethodClass.method(): MethodClass
    for MethodClass in CmdMethod.__subclasses__()
}


def get_cmd_method(method):
    """Returns the 'CmdMethod' to handle 'method'."""
    return METHOD_CLASSES.get(method, CmdMethod)()
