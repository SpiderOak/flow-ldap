"""
team_handler.py

Process org-member-event notifications.
"""

import logging

from flow import Flow

from src.flowpkg import flow_util


LOG = logging.getLogger("team_handler")


class TeamMemberEventHandler(object):
    """Processes org-member-event notifications.
    If an account has been flagged as admin of the LDAP Team,
    then the DMA adds the account to the LOG channel.
    """

    def __init__(self, dma_manager):
        self.dma_manager = dma_manager
        self.notif_types = [Flow.ORG_MEMBER_NOTIFICATION]

    def callback(self, _notif_type, notif_data):
        """Callback for org-member-event, if the account was marked
        as admin of the LDAP team, then it is automatically added to
        the LOG channel.
        """
        for ome in notif_data:
            if ome["orgId"] == self.dma_manager.ldap_team_id and \
               ome["state"] == "a":
                flow_util.add_account_to_channels(
                    self.dma_manager.flow,
                    ome["accountId"],
                    self.dma_manager.ldap_team_id,
                    [self.dma_manager.log_cid],
                )
