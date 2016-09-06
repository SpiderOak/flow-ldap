"""
ldap_sync.py

LDAP sync operation.
TODO: document here all that happens on a sync.
"""

import logging
import threading

from src.sync import action


LOG = logging.getLogger("ldap_sync")


class LDAPSync(object):
    """Runs the LDAP sync operation."""

    def __init__(self, server):
        self.server = server
        self.dma_manager = server.dma_manager
        self.flow_ready = server.dma_manager.ready
        self.flow = server.dma_manager.flow
        self.ldap_factory = server.ldap_factory
        self.config = server.config
        self.sync_on = server.ldap_sync_on
        self.lock = threading.Lock()

    def get_ldap_userlist(self):
        """Retrieves the LDAP user directory using the config group_dn."""
        ldap_conn = self.ldap_factory.get_connection()
        group_dn = self.config.get("group-dn")
        group = ldap_conn.get_group(group_dn)
        group_users = group.userlist()
        excluded_accounts = self.config.get_list("excluded-accounts")
        users = [user for user in group_users if user[
            "email"] not in excluded_accounts]
        ldap_conn.close()
        return users

    def changes_into_actions(self, delta_changes):
        """Turns the given delta changes into executable action objects."""
        action_labels = {
            "retry_setup": action.TryUserAccountSetup,
            "setup": action.UserAccountSetup,
            "update_lock": action.UpdateLock,
        }
        actions = []
        for action_label, entries in delta_changes.iteritems():
            for entry in entries:
                actions.append(action_labels[action_label](self, entry))
        return actions

    def execute_actions(self, actions):
        """Executes all the actions needed to comply with the LDAP sync."""
        for action_i in actions:
            try:
                success = action_i.execute()
                if not success:
                    LOG.error(
                        "action %s execution failed", 
                        action_i,
                    )
            except Exception as exception:
                LOG.error(
                    "action %s execution failed with error: %s", 
                    action_i, 
                    exception,
                )

    def pre_checks(self):
        if not self.flow_ready.is_set():
            LOG.info("flow not ready, skip run")
            return False
        if not self.sync_on.is_set():
            LOG.info("sync disabled, skip run")
            return False
        return True

    def trigger_sync(self):
        LOG.debug("triggering a ldap sync")
        threading.Thread(
            target=self.run_sync,
        ).start()

    def run_sync(self):
        self.lock.acquire()
        try:
            self.run()
        finally:
            self.lock.release()

    def run(self):
        """Runs the actual LDAP sync operation."""
        if not self.pre_checks():
            return
        LOG.debug("start")
        try:
            ldap_accounts = self.get_ldap_userlist()
        except Exception as exception:
            LOG.error("Failed to get ldap userlist: '%s'", str(exception))
            return
        LOG.debug("ldap accounts: %s", ldap_accounts)
        delta_changes = self.server.db.delta(ldap_accounts)
        actions = self.changes_into_actions(delta_changes)
        LOG.debug("actions to execute: %s", actions)
        self.execute_actions(actions)
        LOG.debug("done")
