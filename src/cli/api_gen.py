"""
api_gen.py

Utilities for automatic API generation.
"""

from src.http.http_api import HttpApi


def get_method_doc(method):
    """Parses the method __doc__ and returns
    method doc together with argument doc.
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


def add_api_methods(parser):
    """Adds an argument parser for each API method (add_parser),
    together with arguments (add_argument) for their function arguments.
    Arguments:
    parser : argparse.ArgumentParser instance
    """
    api_methods = HttpApi.get_apis()
    for method_name, method in api_methods:
        method_arg_name = method_name.replace("_", "-")
        api_doc_method, args_doc = get_method_doc(method)
        method_parser = parser.add_parser(
            method_arg_name, description=api_doc_method, help=api_doc_method)
        method_parser.set_defaults(api=method_arg_name)
        method_args = HttpApi.get_api_args(method_name)
        for arg in method_args:
            arg_doc = "Doc N/A."
            arg = arg.replace("_", "-")
            required = True
            if arg in args_doc:
                arg_doc = args_doc[arg]
                if "[optional]" in arg_doc:
                    arg_doc = arg_doc.replace("[optional]", "")
                    required = False
            method_parser.add_argument(
                "--" + arg,
                metavar="X",
                help=arg_doc,
                required=required,
            )
