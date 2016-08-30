"""
chan_handler.py

"""

import logging

from flow import Flow

from src.flowpkg import flow_util


LOG = logging.getLogger("chan_handler")


class ChannelMemberEventHandler(object):

    def __init__(self, server):
        self.server = server
        self.flow = server.flow
        self.notif_types = [Flow.CHANNEL_MEMBER_NOTIFICATION]

    def callback(self, _notif_type, notif_data):
        account_id = self.flow.account_id()
        for cme in notif_data:
            if account_id == cme["accountId"] and \
               cme["state"] == "a":
                accounts = self.server.db.get_ldaped_accounts()
                flow_util.rescan_accounts_on_channel(
                    self.flow,
                    self.server.ldap_team_id,
                    cme["channelId"],
                    accounts,
                )
