"""
action.py

Action classes to execute on an ldap-sync run.
"""

import logging
from flow import Flow

from src.flowpkg import flow_util


LOG = logging.getLogger("action")


class Action(object):
    """Main abstract action class.
    It represents an action to be executed on the ldap-sync run.
    """

    def __init__(self, ldap_sync, ldap_account):
        self.ldap_sync = ldap_sync
        self.ldap_account = ldap_account
        self.log = logging.getLogger(self.name())

    def name(self):
        """Returns the name of the action class."""
        return self.__class__.__name__

    def execute(self):
        """Action to execute on this action class."""
        LOG.error(
            "%s: execute not implemented",
            self.name(),
        )
        return False

    def __repr__(self):
        """String representation of actions to print to logging."""
        str_repr = "{%s:" % self.name()
        if self.ldap_account:
            row_str = "["
            for key in self.ldap_account.keys():
                row_str += "%s=%s," % (key, self.ldap_account[key])
            row_str += "]"
            str_repr += "ldap=%s" % row_str
        else:
            str_repr += "ldap=N/A"
        str_repr += "}"
        return str_repr


class UserAccountSetup(Action):
    """Action to create the account on the semaphor
    service and update the database.
    """

    def add_account_to_team_chans(self, account_id):
        """Adds the given account to the LDAP Team and
        prescribed channels."""
        cids = flow_util.get_prescribed_cids(
            self.ldap_sync.flow,
            self.ldap_sync.dma_manager.ldap_team_id,
        )
        LOG.info("prescribed channels: %s", cids)
        flow_util.add_account_to_team_chans(
            self.ldap_sync.flow,
            account_id,
            self.ldap_sync.dma_manager.ldap_team_id,
            cids,
        )
        return True

    def execute(self):
        """Executes the user setup action, which consists of:
        1. call setup_ldap_account on flow.
        2. create db entry on the local db.
        """
        flow_account_exists = False
        username = self.ldap_account["email"]
        try:
            setup_response = \
                self.ldap_sync.flow.setup_ldap_account(
                    username=username,
                )
        except Flow.FlowError as flow_err:
            if str(flow_err) == "Duplicate entry":
                flow_account_exists = True
            else:
                self.log.error(
                    "setup_ldap_account(%s) failed: %s",
                    username,
                    flow_err,
                )
                return False

        if flow_account_exists:
            # Lock the account on the flow service with 'ldap lock'
            try:
                self.ldap_sync.flow.set_account_lock(
                    username=username,
                    lock_type=Flow.LDAP_LOCK,
                )
            except Flow.FlowError as flow_err:
                self.log.error(
                    "set_account_lock(%s) failed: %s",
                    username,
                    flow_err,
                )
                return False
            semaphor_data = {
                "lock_state": Flow.LDAP_LOCK,
            }
        else:
            # Create a fresh entry on the local DB
            semaphor_data = {
                "id": self.ldap_sync.flow.get_peer(username)["accountId"],
                "password": setup_response["password"],
                "L2": setup_response["level2Secret"],
                "lock_state": Flow.UNLOCK,
            }

        # Create the entry on the local DB
        self.ldap_sync.server.db.create_account(
            self.ldap_account,
            semaphor_data,
        )

        if "id" in semaphor_data:
            response = self.add_account_to_team_chans(semaphor_data["id"])
        else:
            response = True
        return response


class UpdateLock(Action):
    """Updates the internal lock state and also
    updates the lock state on the flow service.
    """

    def execute(self):
        """Updates the 'enabled' and 'lock_state' on the local DB
        and updates the lock state in the flow service.
        It only locks/unlocks a Semaphor account if the current lock_state
        is not ldap-locked.
        """
        username = self.ldap_account["email"]
        lock_type = Flow.UNLOCK \
            if self.ldap_account["enabled"] \
            else Flow.FULL_LOCK
        try:
            if self.ldap_account["lock_state"] != Flow.LDAP_LOCK:
                self.ldap_sync.flow.set_account_lock(
                    username=username,
                    lock_type=lock_type,
                )
        except Flow.FlowError as flow_err:
            self.log.error(
                "set_account_lock(%s) failed: %s",
                username,
                flow_err,
            )
            return False
        # Update the database with the new 'enabled' state
        return self.ldap_sync.server.db.update_lock(self.ldap_account)


class TryUserAccountSetup(UserAccountSetup):
    """Action to retry the user account
    setup for an 'ldap lock'ed account.
    If this succeeds then it means the user chose
    to change his Semaphor username.
    So this allows the bot to take control of the account.
    """

    def execute(self):
        """Tries to execute the user setup action, which consists of:
        1. call setup_ldap_account on flow.
        2. update db entry on the local db if it succeeded.
        """
        username = self.ldap_account["email"]
        try:
            setup_response = \
                self.ldap_sync.flow.setup_ldap_account(
                    username=username,
                )
        except Flow.FlowError as flow_err:
            if str(flow_err) == "Duplicate entry":
                # Nothing to do
                return True
            else:
                self.log.error(
                    "setup_ldap_account(%s) failed: %s",
                    username,
                    flow_err,
                )
                return False

        # Username has been freed
        # So let's update the semaphor entry on the local DB
        semaphor_data = {
            "id": self.ldap_sync.flow.get_peer(username)["accountId"],
            "password": setup_response["password"],
            "L2": setup_response["level2Secret"],
            "lock_state": Flow.UNLOCK,
        }

        self.ldap_sync.server.db.update_semaphor_account(
            username,
            semaphor_data,
        )
        return self.add_account_to_team_chans(semaphor_data["id"])
