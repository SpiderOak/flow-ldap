"""
ldap_factory.py


"""


import ldap_reader


# TODO: use reload_config, TBD
class LDAPFactory(object):
    
    def __init__(self, config):
        self.config = config
        self.reload_config()

    def reload_config(self):
        self.uri = self.config.get("uri")
        self.base_dn = self.config.get("base-dn")
        self.admin_user = self.config.get("admin-user")
        self.admin_pw = self.config.get("admin-pw")
        self.ldap_vendor_map = {
            "server_type": self.config.get("server-type"),
            "dir_member_source": self.config.get("dir-member-source"),
            "dir_username_source": self.config.get("dir-username-source"),
            "dir_fname_source": self.config.get("dir-fname-source"),
            "dir_lname_source": self.config.get("dir-lname-source"),
            "dir_guid_source": self.config.get("dir-guid-source"),
            "dir_auth_source": self.config.get("dir-auth-source"),
        }

    def get_connection(self):
        return ldap_reader.LdapConnection(
            self.uri,
            self.base_dn,
            self.admin_user,
            self.admin_pw,
            self.ldap_vendor_map,
        )
