"""
ldap_bind_req_handler.py

Handler for the users LDAP bind requests.
"""

import threading
import logging

from flow import Flow

from src.db import local_db
from src.flowpkg import flow_util


LOG = logging.getLogger("ldap_bind_req_handler")


class LDAPBindRequestHandler(object):
    """Runs the LDAP auth/bind request handler."""

    def __init__(self, dma_manager):
        self.dma_manager = dma_manager
        self.notif_types = [Flow.LDAP_BIND_REQUEST_NOTIFICATION]

    def callback(self, _notif_type, notif_data):
        """Callback to execute for 'ldap-bind-request' notifications.
        It spawns a new thread to process each bind request.
        """
        LOG.debug(
            "bind request received from '%s'",
            notif_data["username"],
        )
        LDAPBindProcessor(self, notif_data).start()


class LDAPBindProcessor(threading.Thread):

    def __init__(self, ldap_bind_handler, notif_data):
        super(LDAPBindProcessor, self).__init__()
        self.flow = ldap_bind_handler.dma_manager.flow
        self.ldap_factory = ldap_bind_handler.dma_manager.ldap_factory
        self.db = ldap_bind_handler.dma_manager.db
        self.ldap_tid = ldap_bind_handler.dma_manager.ldap_team_id
        self.notif_data = notif_data

    def run(self):
        """It executes the actual bind request."""
        username = self.notif_data["username"]
        account_entry = self.db.get_account(username)
        if not account_entry:
            LOG.error("account '%s' not found", username)
            return
        if not account_entry["enabled"]:
            LOG.debug("account '%s' is disabled, cannot bind", username)
            return
        if self.notif_data["level2Secret"]:
            self.process_link_request(
                self.notif_data,
                account_entry,
            )
        else:
            self.process_create_ldap_device_request(
                self.notif_data,
                account_entry,
            )

    def process_link_request(self, notif_data, account_entry):
        """It executes the link request, which involves:
        1. Bind against LDAP server, if successful, then
        2. Execute flow operation to link account to LDAP,
        if successful, then
        3. Update DB, marking the account as LDAPed and store
        generated password and L2.
        (via link_ldap_account API).
        """
        username = notif_data["username"]
        if account_entry["lock_state"] != Flow.LDAP_LOCK:
            LOG.error(
                "cannot link non-ldap-locked account '%s'",
                username,
            )
            return
        if not self.ldap_bind(username, notif_data["password"]):
            LOG.debug("ldap_bind(%s) failed", username)
            return
        try:
            password = self.flow.link_ldap_account(
                username=username,
                secure_exchange_token=notif_data["secureExchangeToken"],
                level2_secret=notif_data["level2Secret"],
            )
        except Flow.FlowError as flow_err:
            LOG.error(
                "link_ldap_account(%s) failed: %s",
                username,
                flow_err,
            )
            return
        # Account is in control of the bot now, update data
        semaphor_data = {
            "semaphor_guid": self.flow.get_peer(username)["accountId"],
            "password": password,
            "L2": notif_data["level2Secret"],
            "lock_state": Flow.UNLOCK,
        }
        self.db.update_semaphor_account(username, semaphor_data)
        # Add account to LDAP team and prescribed channels
        prescr_cids = flow_util.get_prescribed_cids(
            self.flow,
            self.ldap_tid,
        )
        flow_util.add_account_to_team_chans(
            self.flow,
            semaphor_data["semaphor_guid"],
            self.ldap_tid,
            prescr_cids,
        )

    def process_create_ldap_device_request(self,
                                           notif_data,
                                           account_entry):
        """The following is executed:
        1. Bind against LDAP server, if successful, then
        2. Get user's L2 from the DB, if successful, then
        3. Send L2 to the server to allow the device creation
        (via ldap_bind_response API).
        """
        username = notif_data["username"]
        if account_entry["lock_state"] != Flow.UNLOCK:
            LOG.error(
                "cannot allow device creation "
                "to non-ldaped account '%s'",
                username,
            )
            return
        if not self.ldap_bind(username, notif_data["password"]):
            LOG.debug("ldap_bind(%s) failed", username)
            return
        self.flow.ldap_bind_response(
            username=username,
            secure_exchange_token=notif_data["secureExchangeToken"],
            level2_secret=account_entry["L2"],
        )

    def ldap_bind(self, username, password):
        """Executes the actual bind against the LDAP server.
        Returns True if the credentials are correct.
        """
        ldap_conn = self.ldap_factory.get_connection()
        response = ldap_conn.can_auth(
            username,
            password,
        )
        ldap_conn.close()
        return response
