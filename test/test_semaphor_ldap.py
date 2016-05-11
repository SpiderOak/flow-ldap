#! /usr/bin/env python
"""
test_semaphor_ldap.py

Tests semaphor-ldap client and server mode

usage:
./test/test_semaphor_ldap.py
for debugging:
./test/test_semaphor_ldap.py --debug
"""
import sys
import unittest
import os
import multiprocessing
import logging
import shutil
import ConfigParser
import ast
import time

from scripttest import TestFileEnvironment
from mock import (
    patch,
    Mock,
    MagicMock,
)

from src.server import Server
from src.cli import Cli
import src.common


DEBUG = False
SEMLDAP_CONFIGDIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config"
)

os.environ["SEMLDAP_CONFIGDIR"] = SEMLDAP_CONFIGDIR
# Environment for command-line tests
ENV = TestFileEnvironment(
    environ=os.environ,
)


class TestClientServer(unittest.TestCase):
    """Test the client interaction with server."""

    def setUp(self):

        self.mock_group_users = [
            {
                u"lastname": u"Last1",
                u"uniqueid": u"2ec71bb6-8ac8-1035-8a65-319da04237b4",
                u"enabled": True,
                u"email": u"test1",
                u"firstname": u"Test1",
            },
            {
                u"lastname": u"Last2",
                u"uniqueid": u"a6e83bd8-8ac9-1035-8a69-319da04237b4",
                u"enabled": True,
                u"email": u"test2",
                u"firstname": u"Test2",
            },
            {
                u"lastname": u"Last3",
                u"uniqueid": u"7c67a9ee-8ac8-1035-8a67-319da04237b4",
                u"enabled": False,
                u"email": u"test3",
                u"firstname": u"Test3",
            },
        ]

        # Get full path of main script
        self.main_script = os.path.join(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "src"),
            "semaphor_ldap.py"
        )

        self.patches = {
            "src.server.Server.init_ldap": Mock(),
            "src.server.Server.init_flow": Mock(),
            "src.server.Server.init_cron": Mock(),
            "src.server.Server.run_flow": Mock(),
        }
        self.applied_patches = [
            patch(patch_name, data)
            for patch_name, data in self.patches.items()
        ]
        for applied_patch in self.applied_patches:
            applied_patch.start()

        server_config_map = {
            "Server": {
                "listen_address": "localhost",
                "listen_port": "8080",
            },
            "Semaphor": {
                "username": "Account",
                "password": "Password",
                "server_uri": "flow.spideroak.com",
                "device_name": "Device",
                "phone_number": "123456789",
            },
            "LDAP": {
                "uri": "ldap://127.0.1.1",
                "base_dn": "dc=example,dc=com",
                "admin_user": "cn=admin,dc=example,dc=com",
                "admin_pw": "password",
                "group_dn": "cn=Group,dc=example,dc=com",
                "poll_group_minutes": "5",
            },
            "LDAP Vendor": {
                "server_type": "OpenLDAP",
                "dir_member_source": "member",
                "dir_username_source": "uid",
                "dir_fname_source": "givenName",
                "dir_lname_source": "sn",
                "dir_guid_source": "entryUUID",
                "dir_auth_source": "dn",
            },
        }

        server_options = MagicMock()
        server_options.debug = DEBUG

        # Temporarily patch loading config from file
        with patch.object(
                ConfigParser.RawConfigParser,
                "read"
            ), \
            patch.object(
                src.common,
                "raw_config_as_dict",
                return_value=server_config_map
        ), \
            patch.object(
                os.path,
                "isfile",
                return_value=True
        ):
            server = Server(server_options)

        # Mock LDAPConnection 'can_auth' response
        server.ldap_conn = Mock()
        server.ldap_conn.can_auth = Mock()
        server.ldap_conn.can_auth.return_value = True

        # Mock LDAPConnection 'group_userlist' response
        group = Mock()
        group.userlist.return_value = self.mock_group_users
        server.ldap_conn.get_group = Mock()
        server.ldap_conn.get_group.return_value = group

        # Run the server
        self.server_process = multiprocessing.Process(target=server.run)
        self.server_process.start()
        time.sleep(2)

    def test_can_auth(self):
        """Run the client 'can-auth' option."""
        cli_options = MagicMock()
        cli_options.debug = DEBUG
        cli_options.api = "can-auth"
        cli_options.username = "account"
        cli_options.password = "password"
        cli = Cli(cli_options)
        self.assertEqual(cli.run(), True)

        # Test the same operation but from command line
        result = ENV.run(
            script="%s client can-auth --username account --password password"
            % self.main_script,
        )
        self.assertEqual(result.returncode, os.EX_OK)
        self.assertEqual(result.stdout, "True\n")

    def test_group_userlist(self):
        """Test the client 'group-userlist' option"""
        cli_options = MagicMock()
        cli_options.debug = DEBUG
        cli_options.api = "group-userlist"
        cli_options.group_dn = "cn=Group,dc=example,dc=com"
        cli = Cli(cli_options)
        self.assertEqual(cli.run(), self.mock_group_users)

        # Test the same operation but from command line
        result = ENV.run(
            script="%s client group-userlist --group-dn "
            "\"cn=Group,dc=example,dc=com\"" % self.main_script,
        )
        self.assertEqual(result.returncode, os.EX_OK)
        self.assertEqual(
            ast.literal_eval(
                result.stdout),
            self.mock_group_users)

    def test_log_dest(self):
        """Test the client 'log-dest' option"""
        cli_options = MagicMock()
        cli_options.debug = DEBUG
        cli_options.api = "log-dest"
        cli_options.target = "file"
        cli = Cli(cli_options)
        self.assertEqual(cli.run(), "Success")

        # Test the same operation but from command line
        result = ENV.run(
            script="%s client log-dest --target file" % self.main_script,
        )
        self.assertEqual(result.returncode, os.EX_OK)
        self.assertEqual(result.stdout, "Success\n")

    def tearDown(self):
        """Closes patches and terminates server started on setUp."""
        for applied_patch in self.applied_patches:
            applied_patch.stop()
        if os.path.isdir(SEMLDAP_CONFIGDIR):
            shutil.rmtree(SEMLDAP_CONFIGDIR)
        self.server_process.terminate()


def setup_logging():
    """Setup logging only if --debug command line was provided."""
    if DEBUG:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(name)-12s: %(levelname)-8s %(message)s")
        console.setFormatter(formatter)
        logging.getLogger("").addHandler(console)
        logging.getLogger("").setLevel(logging.DEBUG)
        logging.getLogger("requests").setLevel(logging.WARNING)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        DEBUG = True
        sys.argv.remove("--debug")
    setup_logging()
    unittest.main()
