"""
ldap_sync.py

LDAP sync operation. 
TODO: document here all that happens on a sync.
"""

import logging

import schedule

from src import server_config
import action

LOG = logging.getLogger("ldap_sync")


class LDAPSync(object):
    """Runs the LDAP sync operation."""

    def __init__(self, server):
        self.flow = server.flow
        self.ldap_factory = server.ldap_factory
        self.db = server.db
        self.config = server.config
        self.ldap_tid = server.ldap_team_id
        self.config = server.config
        self.sync_on = server.sync_on
        self.flow_ready = server.flow_ready

    def get_ldap_userlist(self):
        """Retrieves the LDAP user directory using the config group_dn."""
        ldap_conn = self.ldap_factory.get_connection()
        group_dn = self.config.get("group-dn")
        group = ldap_conn.get_group(group_dn)
        group_users = group.userlist()
        excluded_accounts = self.config.get_list("excluded-accounts")
        users = [user for user in group_users if user["email"] not in excluded_accounts]
        return users

    def changes_into_actions(self, delta_changes):
        """Turns the given delta changes into executable action objects."""
        action_labels = {
            "setup": action.UserAccountSetup,
            "update_lock": action.UpdateLock,
            "retry_setup": action.TryUserAccountSetup,
            "update_ldap_data": action.UpdateLDAPData,
        }
        actions = []
        for action_label, entries in delta_changes.iteritems():
            for entry in entries:
                actions.append(action_labels[action_label](self, entry))
        return actions

    def execute_actions(self, actions):
        """Executes all the actions needed to comply with the LDAP sync."""
        for action in actions:
            success = action.execute()
            if not success:
                LOG.error("action %s execution failed", action)

    def run(self):
        """Runs the actual LDAP sync operation."""
        if not self.sync_on.is_set():
            LOG.info("sync disabled, skip run")
            return
        if not self.flow_ready.is_set():
            LOG.info("flow not ready, skip run")
            return
        LOG.debug("start")
        try:
            ldap_accounts = self.get_ldap_userlist()
        except Exception as exception:
            LOG.error("Failed to get ldap userlist: '%s'", str(exception))
            return
        LOG.debug("ldap accounts: %s", ldap_accounts)
        delta_changes = self.db.delta(ldap_accounts)
        actions = self.changes_into_actions(delta_changes)
        LOG.debug("actions to execute: %s", actions)
        self.execute_actions(actions)
        LOG.debug("done")
