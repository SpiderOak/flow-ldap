"""
http_handler.py

HTTP request handler for the local HTTP Semaphor-LDAP server.
"""

import logging
import hmac

from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Request, Response
from werkzeug.datastructures import Headers
from jsonrpc import JSONRPCResponseManager, dispatcher

from src import utils
from src.http.http_api import HttpApi


LOG = logging.getLogger("http_handler")


class HTTPRequestHandler(object):
    """Handles/Dispatches HTTP requests."""

    def __init__(self, server, http_server):
        """Arguments:
        server : server.Server instance
        """
        self.http_api = HttpApi(server, http_server)
        self.auth_token = http_server.auth_token
        self.register_api_methods()
        url_path = "/" + utils.SERVER_JSON_RPC_URL_PATH
        self.url_map = Map([
            Rule(url_path, endpoint="rpc_handler", methods=["POST"]),
            Rule(url_path, endpoint="preflight", methods=["OPTIONS"])
        ])

    @staticmethod
    def preflight(_request):
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

    def rpc_handler(self, request):
        """Method to dispatch JSON-RPC requests.
        Arguments:
        request : werkzeug.wrappers.Request instance.
        """
        auth_token = request.environ.get("HTTP_AUTH_TOKEN")
        if not auth_token or \
           not hmac.compare_digest(auth_token, self.auth_token):
            return Response("Invalid Request", status=404)
        rpc_response = JSONRPCResponseManager.handle(
            request.data,
            dispatcher,
        )
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
