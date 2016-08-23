"""
chan_handler.py

"""

import logging

from flow import Flow

from src.flowpkg import flow_util


LOG = logging.getLogger("chan_handler")


class ChannelMemberEventHandler(object):

    def __init__(self, server):
        self.flow = server.flow
        self.db = server.db
        self.ldap_tid = server.ldap_team_id
        self.account_id = self.flow.account_id()
        self.notif_types = [Flow.CHANNEL_MEMBER_NOTIFICATION]

    def callback(self, _notif_type, notif_data):
        for cme in notif_data:
            if self.account_id == cme["accountId"] and \
               cme["state"] == "a":
                accounts = self.db.get_ldaped_accounts()
                flow_util.rescan_accounts_on_channel(
                    self.flow,
                    self.ldap_tid,
                    cme["channelId"],
                    accounts,
                )
