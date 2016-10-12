"""
chan_handler.py

Processes the channel-member-event notifications.
"""

import logging

from flow import Flow

from src.flowpkg import flow_util


LOG = logging.getLogger("chan_handler")


class ChannelMemberEventHandler(object):
    """Processes the channel-member-event notifications.
    It checks if the DMA was added to a channel as admin
    (this turns the channel into a prescribed channel),
    and if that's the case, it performs rescan to add all
    DB accounts to the new prescribed channel.
    """

    def __init__(self, dma_manager):
        self.dma_manager = dma_manager
        self.notif_types = [Flow.CHANNEL_MEMBER_NOTIFICATION]

    def callback(self, _notif_type, notif_data):
        """Callback to execute on channel-member-event notification."""
        account_id = self.dma_manager.flow.account_id()
        for cme in notif_data:
            if account_id == cme["accountId"] and \
               cme["state"] == "a":
                accounts = self.dma_manager.db.get_enabled_ldaped_accounts()
                flow_util.rescan_accounts_on_channel(
                    self.dma_manager.flow,
                    self.dma_manager.ldap_team_id,
                    cme["channelId"],
                    accounts,
                )
