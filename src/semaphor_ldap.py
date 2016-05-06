#! /usr/bin/env python

"""
semaphor_ldap.py

semaphor-ldap application main script.
"""

import sys
import os
import argparse
import logging
import time
import signal

import common
from cli import Cli
from server import Server
import http


LOG = logging.getLogger("semaphor-ldap")


def run_cli(options):
    """Run the Cli object."""
    cli = Cli(options)
    # For now let's throw Cli.run() to stdout
    print("%s" % cli.run())


# TODO: Mainly needed for semaphor-backend, this will not
# be needed once semaphor-backend exits after orphaned.
def signal_handler(sig, frame):
    """Function to gracefully terminate.
    sys.exit will raise SystemExit that
    should be deal with.
    """
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def run_server(options):
    """Run the Server object."""

    server = Server(options)

    try:
        server.run()
    finally:  # Also catches SystemExit
        server.cleanup()


def setup_server_logging(debug):
    """Setup logging configuration for the Server mode."""

    # Log to file handler
    log_file_name = time.strftime("%Y%m%d-%H%M%S.log")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        datefmt="%m-%d %H:%M",
        filename=log_file_name,
        filemode="w")

    # Log to console sys.stderr
    console = logging.StreamHandler()
    if debug:
        console.setLevel(logging.DEBUG)
    else:
        console.setLevel(logging.INFO)

    # set a format which is simpler for console use
    formatter = logging.Formatter("%(name)-12s: %(levelname)-8s %(message)s")
    console.setFormatter(formatter)

    logging.getLogger('').addHandler(console)


def setup_cli_logging(debug):
    """Setup logging configuration for the CLI mode."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s")


def setup_logging(server_mode, debug):
    """Setup logging configuration for the application."""
    if server_mode:
        setup_server_logging(debug)
    else:
        setup_cli_logging(debug)
    # Do not show 'requests' lib INFO logs
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("flow").setLevel(
        logging.DEBUG if debug else logging.INFO)


def get_method_doc(method):
    """Returns method doc together with argument doc.
    Arguments:
    method : function object
    Returns tuple with method_doc string and a dict with
    {arg_name -> arg_doc}.
    """
    method_doc = "Doc N/A."
    args_doc = {}
    if method.__doc__:
        # Get method documentation
        doc_lines = [line.strip() for line in method.__doc__.splitlines()]
        method_doc = doc_lines[0]
        # Get arguments documentation
        if "Arguments:" in doc_lines:
            arguments_index = doc_lines.index("Arguments:")
            for i in range(arguments_index + 1, len(doc_lines)):
                args_line = doc_lines[i]
                if args_line:
                    arg_name_desc = args_line.split(":", 1)
                    arg_name = arg_name_desc[0].strip().replace("_", "-")
                    args_doc[arg_name] = arg_name_desc[1].strip()
    return method_doc, args_doc


def add_api_methods(subparsers):
    """Adds an argument parser for each API method (add_parser),
    together with arguments (add_argument) for their function arguments.
    Arguments:
    subparsers : ArgumentParser instance
    """
    api_methods = http.HttpApi.get_apis()
    for method_name, method in api_methods:
        method_arg_name = method_name.replace("_", "-")
        api_doc_method, args_doc = get_method_doc(method)
        method_parser = subparsers.add_parser(
            method_arg_name, help=api_doc_method)
        method_parser.set_defaults(api=method_arg_name)
        method_args = http.HttpApi.get_api_args(method_name)
        for arg in method_args:
            arg_doc = "Doc N/A."
            arg = arg.replace("_", "-")
            if arg in args_doc:
                arg_doc = args_doc[arg]
            method_parser.add_argument(
                "--" + arg,
                metavar="X",
                help=arg_doc,
                required=True)


def parse_options(argv):
    """Command line options parsing."""

    parser = argparse.ArgumentParser(
        description="semaphor-ldap is a daemon/cli to enable the use of "
                    "Semaphor with Customer LDAP credentials.")
    parser.add_argument("--version", action="version", version=common.VERSION)

    # Generic config
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Debug Mode",
        default=False)

    subparsers = parser.add_subparsers(title="Modes")

    # Server config
    server_parser = subparsers.add_parser("server", help="Server Mode")
    server_parser.set_defaults(server_mode=True)
    server_parser.add_argument(
        "--config",
        metavar="CONFIG",
        help="Config cfg file with LDAP and Semaphor settings")

    # CLI config
    cli_parser = subparsers.add_parser("client", help="Client Mode")
    cli_parser.set_defaults(server_mode=False)

    # Add API methods
    cli_subparsers = cli_parser.add_subparsers(title="Commands")
    add_api_methods(cli_subparsers)

    options = parser.parse_args(argv[1:])

    setup_logging(options.server_mode, options.debug)

    # Check config file
    if options.server_mode and \
            (not options.config or not os.path.isfile(options.config)):
        LOG.error("Must provide a cfg file, see --help.")
        sys.exit(os.EX_USAGE)

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
