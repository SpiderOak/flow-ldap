"""
ldap_factory.py


"""

import logging
import threading

import ldap_reader


LOG = logging.getLogger("ldap_factory")


class LDAPFactory(object):

    def __init__(self, config):
        self.lock = threading.Lock()
        self.config = config
        self.reload_config()

    def reload_config(self):
        LOG.debug("reloading ldap config")
        self.lock.acquire()
        self.uri = self.config.get("uri")
        self.base_dn = self.config.get("base-dn")
        self.admin_user = self.config.get("admin-user")
        self.admin_pw = self.config.get("admin-pw")
        self.ldap_vendor_map = {
            "server_type": self.config.get("server-type"),
            "dir_member_source": self.config.get("dir-member-source"),
            "dir_username_source": self.config.get("dir-username-source"),
            "dir_guid_source": self.config.get("dir-guid-source"),
            "dir_auth_source": self.config.get("dir-auth-source"),
        }
        self.lock.release()

    def get_connection(self, timeout=5):
        self.lock.acquire()
        try:
            ldap_conn = ldap_reader.LdapConnection(
                self.uri,
                self.base_dn,
                self.admin_user,
                self.admin_pw,
                self.ldap_vendor_map,
                timeout=timeout,
            )
        finally:
            self.lock.release()
        return ldap_conn

    def check_connection(self):
        ldap_conn = self.get_connection()
        ldap_conn.close()
