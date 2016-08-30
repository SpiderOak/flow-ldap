"""
team_handler.py

"""

import logging

from flow import Flow

from src.flowpkg import flow_util


LOG = logging.getLogger("team_handler")


class TeamMemberEventHandler(object):

    def __init__(self, server):
        self.server = server
        self.flow = server.flow
        self.notif_types = [Flow.ORG_MEMBER_NOTIFICATION]

    def callback(self, _notif_type, notif_data):
        for ome in notif_data:
            if ome["orgId"] == self.server.ldap_team_id and \
               ome["state"] == "a":
                flow_util.add_account_to_channels(
                    self.flow,
                    ome["accountId"],
                    self.server.ldap_team_id,
                    [self.server.log_cid],
                )
