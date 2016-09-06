#! /usr/bin/env python

"""
semaphor_ldap.py

semaphor-ldap application main script.
"""

from __future__ import print_function
import os
import sys
import argparse
import logging
import signal
import threading

from src import utils
from src.cli.cmd_cli import CmdCli
from src.cli import api_gen
from src.server import Server
from src.log import app_log


LOG = logging.getLogger("semaphor-ldap")


def run_cli(options):
    """Run the CmdCli object."""
    cli_obj = CmdCli(options)
    cli_obj.run()


def add_cli_options(parser):
    # Add API methods
    cli_subparsers = parser.add_subparsers(
        title="Commands", metavar="{API COMMAND FROM THE LIST}")
    api_gen.add_api_methods(cli_subparsers)


def create_generic_arg_parser():
    parser = argparse.ArgumentParser(
        description="%s is a server/cli app to enable the use of "
                    "Semaphor with Customer LDAP credentials." % (
                        os.path.basename(sys.argv[0])
                    ),
    )
    parser.add_argument("--version", action="version", version=utils.VERSION)
    # Generic config
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Debug Mode",
        default=False,
    )
    return parser


def run_cli_as_default():
    """Run the CmdCli object, to be used in windows
    so we don't have to use the client prefix every time
    we use the client mode.
    """
    parser = create_generic_arg_parser()
    add_cli_options(parser)
    options = parser.parse_args(sys.argv[1:])
    cli_obj = CmdCli(options)
    cli_obj.run()


def signal_handler(sig, frame):
    """Function to gracefully terminate.
    sys.exit will raise SystemExit that
    should be dealt with.
    """
    LOG.debug("termination signal received")
    sys.exit(0)


def run_server(options, stop_server_event=None):
    """Run the Server object."""
    server_obj = None
    try:
        server_obj = Server(options, stop_server_event)
        server_obj.run()
    except Exception as exception:
        LOG.error("server execution failed with '%s'", exception)
        raise  # TODO: remove
    finally:  # Also catches SystemExit
        if server_obj:
            server_obj.cleanup()


def parse_options():
    """Command line options parsing."""
    parser = create_generic_arg_parser()

    subparsers = parser.add_subparsers(title="Modes")

    # Server config
    server_parser = subparsers.add_parser("server", help="Server Mode")
    server_parser.set_defaults(server_mode=True)
    server_parser.add_argument(
        "--config",
        metavar="CONFIG",
        help="Config cfg file with LDAP and Semaphor settings",
    )

    # CLI config
    cli_parser = subparsers.add_parser("client", help="Client Mode")
    cli_parser.set_defaults(server_mode=False)

    # Add client API methods
    add_cli_options(cli_parser)

    options = parser.parse_args(sys.argv[1:])
    return options


def main():
    """Entry point for the application."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    options = parse_options()
    if options.server_mode:
        run_server(options)
    else:  # CLI mode
        run_cli(options)


if __name__ == "__main__":
    if sys.platform == "win32":
        run_cli_as_default()
    else:
        main()
