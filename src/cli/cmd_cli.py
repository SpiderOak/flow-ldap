"""
cmd_cli.py

Command line client mode.
"""

import os
from ConfigParser import RawConfigParser
import logging
import json

import requests

from src import (
    utils,
    app_platform,
)
from src.http.http_api import HttpApi
from src.log import app_log
from src.cli import cmd_method


LOG = logging.getLogger("cmd_cli")


class CmdCli(object):
    """Runs the command line cli mode for this application.
    The cli mode:
      - Executes JSON-RPC requests to the server,
      - Parses the JSON-RPC response
      - Prints the result to stdout.
    """

    def __init__(self, options):
        self.options = options
        self.request_id = 0
        self.server_uri = ""
        self.auth_token = ""
        self.server_config = {}
        app_log.setup_cli_logging(options.debug)

    def load_from_server_config(self):
        """Loads settings from the auto-connect config file
        generated by server. The loaded info allows the
        client to connect to the server.
        """
        autoconnect_file_name = os.path.join(
            app_platform.get_config_path(),
            utils.AUTOCONNECT_CONFIG_FILE_NAME,
        )
        cfg = RawConfigParser()
        with open(autoconnect_file_name, "r") as autoconnect_f:
            cfg.readfp(autoconnect_f)
        self.server_config = utils.raw_config_as_dict(cfg)[
            utils.AUTOCONNECT_CONFIG_SECTION]
        self.server_uri = self.server_config["uri"]
        self.auth_token = self.server_config["auth-token"]

    def run_method(self, method, args_dict):
        """Performs an JSON-RPC request to the server.
        Arguments:
        method : string, method name
        args_dict : dict, positional params
        """
        try:
            self.load_from_server_config()
        except Exception as exception:
            print(
                "ERROR loading the auto-connect config file, error: '%s'.\n"
                "On Windows, this executable must be run in cmd in Administrator mode." % (
                    exception,
                ))
            return
        headers = {
            "content-type": "application/json",
            "auth-token": self.auth_token,
        }
        payload = {
            "method": method,
            "params": args_dict,
            "id": self.request_id,
            "jsonrpc": "2.0",
        }
        LOG.debug("request: %s", payload)
        method_obj = cmd_method.get_cmd_method(method)
        # Preprocess request
        args_dict = method_obj.request(args_dict)
        try:
            response = requests.post(
                self.server_uri,
                data=json.dumps(payload),
                headers=headers,
                timeout=30,
            )
            LOG.debug("response: %s", response.text)
        except requests.RequestException as req_err:
            LOG.debug("Connection error: %s", req_err)
            print "ERROR: Failed to send request to the server"
            return
        try:
            response_data = json.loads(response.text, encoding="utf-8")
        except ValueError as val_err:
            print "Invalid response: '%s'" % val_err
            return
        if self.request_id != response_data.get("id"):
            print (
                "Invalid response, request/response "
                "ids do not match (%s,%s)" % (
                    self.request_id,
                    response_data.get("id"),
                ),
            )
            return
        self.request_id += 1
        # Parse response
        method_obj.response(response_data)

    def run(self):
        """CmdCli command execution.
        Generates the 'params' dict for the JSON request
        from the command line argument method
        (using HttpApi metaprogramming),
        and the executes the JSON-RPC request.
        """
        assert(self.options.api)
        api_name = self.options.api.replace("-", "_")
        args_list = HttpApi.get_api_args(api_name)
        args_dict = {
            key: getattr(self.options, key)
            for key in args_list
        }
        self.run_method(self.options.api, args_dict)
