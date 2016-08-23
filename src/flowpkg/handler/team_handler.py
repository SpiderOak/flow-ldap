"""
team_handler.py

"""

import logging

from flow import Flow

from src.flowpkg import flow_util


LOG = logging.getLogger("team_handler")


class TeamMemberEventHandler(object):

    def __init__(self, server):
        self.flow = server.flow
        self.ldap_tid = server.ldap_team_id
        self.log_cid = server.log_cid
        self.notif_types = [Flow.ORG_MEMBER_NOTIFICATION]

    def callback(self, _notif_type, notif_data):
        for ome in notif_data:
            if ome["orgId"] == self.ldap_tid and \
               ome["state"] == "a":
                flow_util.add_account_to_channels(
                    self.flow,
                    ome["accountId"],
                    self.ldap_tid,
                    [self.log_cid],
                )
