"""
flow_util.py

Set of flow utility functions.
"""

import logging

from flow import Flow

from src import utils, app_platform

LOG = logging.getLogger("flow_util")


def create_flow_object(config):
    flow_config = {
        "host": config.get("flow-service-host") or
        utils.DEFAULT_FLOW_SERVICE_HOST,
        "port": config.get("flow-service-port") or
        utils.DEFAULT_FLOW_SERVICE_PORT,
        "use_tls": config.get("flow-service-use-tls") or
        utils.DEFAULT_FLOW_SERVICE_USE_TLS,
        "flowappglue": config.get("flowappglue") or
        app_platform.get_default_flowappglue_path(),
        "schema_dir": config.get("schema-dir") or
        app_platform.get_default_backend_schema_path(),
        "db_dir": app_platform.get_config_path(),
        "glue_out_filename": app_platform.get_glue_out_filename(),
        "attachment_dir": app_platform.get_default_attachment_path(),
    }
    flow_args = {
        key: value for (key, value) in flow_config.items()
        if value is not None
    }
    flow = Flow(**flow_args)
    flow.set_api_timeout(utils.FLOW_API_TIMEOUT)
    return flow


def get_ldap_team_id(flow):
    teams = flow.enumerate_orgs()
    if len(teams) == 1:
        return teams[0]["id"]
    return None


def is_team_admin(flow, team_id):
    """Returns whether the DMA is admin of the LDAP team."""
    members = flow.enumerate_org_members(team_id)
    is_admin = False
    account_id = flow.account_id()
    for member in members:
        if member["accountId"] == account_id:
            if member["state"] == "a":
                is_admin = True
            break
    return is_admin


def is_member_of_ldap_team(flow):
    """Returns whether the DMA is member of the LDAP team.
    If it is, it also returns the team id.
    """
    return get_ldap_team_id(flow) is not None


def is_channel_admin(flow, channel_id):
    """Returns whether the DMA is admin of the LDAP team."""
    members = flow.enumerate_channel_members(channel_id)
    is_admin = False
    account_id = flow.account_id()
    for member in members:
        if member["accountId"] == account_id:
            if member["state"] == "a":
                is_admin = True
            break
    return is_admin


def add_admins_to_channel(flow, ldap_tid, cid):
    account_id = flow.account_id()
    ldap_admins = [
        member["accountId"]
        for member in flow.enumerate_org_members(ldap_tid)
        if member["state"] in ["a", "o"] and
        member["accountId"] != account_id
    ]
    present_past_members = channel_present_past_members(flow, cid)
    admins_to_add = [
        admin for admin in ldap_admins
        if admin not in present_past_members
    ]
    for admin_id in admins_to_add:
        flow.channel_add_member(
            ldap_tid,
            cid,
            admin_id,
            "m",
        )


def channel_present_past_members(flow, cid):
    members = [
        member["accountId"]
        for member in
        flow.enumerate_channel_member_history(cid)
    ]
    return set(members)


def team_present_members(flow, tid):
    members = [
        member["accountId"]
        for member in
        flow.enumerate_org_members(tid)
    ]
    return set(members)


def team_past_members(flow, tid):
    present_members = team_present_members(flow, tid)
    members = [
        member["accountId"]
        for member in
        flow.enumerate_org_member_history(tid)
        if member["accountId"] not in present_members
    ]
    return set(members)


def add_account_to_channels(flow, account_id, tid, cids):
    for cid in cids:
        past_present_members = channel_present_past_members(flow, cid)
        if account_id not in past_present_members:
            flow.channel_add_member(
                tid,
                cid,
                account_id,
                "m",
            )


def add_account_to_team(flow, account_id, tid):
    present_members = team_present_members(flow, tid)
    if account_id not in present_members:
        past_members = team_past_members(flow, tid)
        if account_id not in past_members:
            flow.org_add_member(
                tid,
                account_id,
                "m",
            )
        else:  # banned
            LOG.info(
                "account '%s' banned from LDAP team",
                flow.get_peer_from_id(account_id)["username"],
            )
            return False
    # already member of the team
    return True


def add_account_to_team_chans(flow, account_id, tid, channel_ids):
    # Add account to team first
    added_to_team = add_account_to_team(flow, account_id, tid)
    if not added_to_team:
        return
    add_account_to_channels(flow, account_id, tid, channel_ids)


def get_prescribed_cids(flow, ldap_tid):
    prescribed_channel_ids = [
        channel["id"] for channel in flow.enumerate_channels(ldap_tid)
        if is_channel_admin(flow, channel["id"])
    ]
    return prescribed_channel_ids


def rescan_accounts_on_channel(flow, ldap_tid, cid, accounts):
    past_present_members = channel_present_past_members(
        flow,
        cid,
    )
    accounts_to_add = [
        account_id for account_id in accounts
        if account_id not in past_present_members
    ]
    for account_id in accounts_to_add:
        flow.channel_add_member(
            ldap_tid,
            cid,
            account_id,
            "m",
        )


def rescan_accounts_on_channels(flow, db, ldap_tid, cids):
    if not cids or not db:
        return
    accounts = db.get_ldaped_accounts()
    if not accounts:
        return
    for cid in cids:
        rescan_accounts_on_channel(flow, ldap_tid, cid, accounts)


def check_flow_connection(flow, tid, cid):
    flow.send_message(
        tid,
        cid,
        "test",
    )
