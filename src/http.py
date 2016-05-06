"""
http.py

HTTP handling for server and CLI communication
"""

import logging
import inspect

from werkzeug.wrappers import Request, Response
from werkzeug.serving import run_simple
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException
from werkzeug.datastructures import Headers
from jsonrpc import JSONRPCResponseManager, dispatcher

import common


LOG = logging.getLogger("http")


class HttpApi(object):
    """HTTP API for this application.
    Public methods defined here are exposed as HTTP API methods,
    and they are also exposed as command line
    arguments on the client
    These methods must:
      - Contain a docstring with the following format:
      '''One line description
      More doc can be added here
      ...
      Arguments:
      arg1 : one line description for arg1.
      arg2 : one line description for arg2.
      '''
      - Method must be public (does not start with _)
      - Method must return a result that can be
        converted to string
    """

    def __init__(self, ldap_conn, flow):
        self.ldap_conn = ldap_conn
        self.flow = flow

    def can_auth(self, username, password):
        """Performs LDAP authentication and returns result.
        Arguments:
        username : Account username.
        password : Account password.
        """
        return self.ldap_conn.can_auth(username, password)

    def group_userlist(self, group_dn):
        """Returns the userlist for a given LDAP Group/OU.
        Arguments:
        group_dn : LDAP Group/OU Distinguished Name.
        """
        ldap_group = self.ldap_conn.get_group(group_dn)
        users = ldap_group.userlist()
        LOG.debug(users)
        return users

    @classmethod
    def get_apis(cls):
        """Helper class method to get all HTTP API method names.
        Returns a list of tuples with (method_name, function object)
        """
        methods = inspect.getmembers(cls, predicate=inspect.ismethod)
        api_methods = []
        for name, method in methods:
            if not name.startswith("_") and \
                    name != "get_apis" and name != "get_api_args":
                api_methods.append((name, method))
        return api_methods

    @classmethod
    def get_api_args(cls, method_name):
        """Helper class method to return
        the argument names of a given function name.
        Arguments:
        method_name : string
        Returns a list with the function argument names.
        """
        func = getattr(cls, method_name)
        args = inspect.getargspec(func).args
        args.remove("self")
        return args


class HTTPRequestHandler(object):
    """Handles/Dispatches HTTP requests."""

    def __init__(self, server):
        """Arguments:
        server : server.Server instance
        """
        self.http_api = HttpApi(server.ldap_conn, server.flow)
        self.register_api_methods()
        url_path = "/" + common.SERVER_JSON_RPC_URL_PATH
        self.url_map = Map([
            Rule(url_path, endpoint="rpc_handler", methods=["POST"]),
            Rule(url_path, endpoint="preflight", methods=["OPTIONS"])
        ])

    @staticmethod
    def preflight(request):
        """Send Preflight response with HTTP POST and OPTIONS.
        Arguments:
        request : werkzeug.wrappers.Request instance.
        """
        headers = Headers()
        headers.add("Access-Control-Allow-Origin", "*")
        headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        headers.add(
            "Access-Control-Allow-Headers",
            "X-Requested-With,content-type")
        headers.add("Access-Control-Allow-Credentials", "true")
        return Response(response="", headers=headers)

    @staticmethod
    def rpc_handler(request):
        """Method to dispatch JSON-RPC requests.
        Arguments:
        request : werkzeug.wrappers.Request instance.
        """
        rpc_response = JSONRPCResponseManager.handle(
            request.data, dispatcher)
        return Response(rpc_response.json, mimetype="application/json")

    def register_api_methods(self):
        """Registers all HttpApi methods to the dispatcher."""
        for method_name, _ in HttpApi.get_apis():
            disp_method_name = method_name.replace("_", "-")
            dispatcher[disp_method_name] = getattr(self.http_api, method_name)

    def dispatch_request(self, request):
        """Performs request dispatching from URL and method.
        Arguments:
        request : werkzeug.wrappers.Request instance.
        """
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, endpoint)(request, **values)
        except HTTPException as http_exception:
            return http_exception

    def __call__(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)


class HTTPServer(object):
    """HTTP server container object. Runs the HTTP server loop."""

    def __init__(self, server):
        self.server = server

    def run(self):
        """Run this HTTP server."""
        app = HTTPRequestHandler(self.server)
        run_simple('localhost', 8080, app)
