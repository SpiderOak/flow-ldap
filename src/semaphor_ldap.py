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


def signal_handler(sig, frame):
    """Function to gracefully terminate.
    sys.exit will raise SystemExit that
    should be dealt with.
    """
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def run_server(options):
    """Run the Server object."""
    server_obj = None
    try:
        server_obj = Server(options)
        server_obj.run()
    except Exception as exception:
        LOG.error("server execution failed with '%s'", exception)
        raise
    finally:  # Also catches SystemExit
        if server_obj:
            server_obj.cleanup()


def parse_options(argv):
    """Command line options parsing."""

    parser = argparse.ArgumentParser(
        description="%s is a daemon/cli to enable the use of "
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

    # Add API methods
    cli_subparsers = cli_parser.add_subparsers(
        title="Commands", metavar="{API COMMAND FROM THE LIST}")
    api_gen.add_api_methods(cli_subparsers)

    options = parser.parse_args(argv[1:])

    return options


def main():
    """Entry point for the application."""
    options = parse_options(sys.argv)
    if options.server_mode:
        run_server(options)
    else:  # CLI mode
        run_cli(options)


if __name__ == "__main__":
    main()
