"""
flow_setup.py

Performs the flow setup process for semaphor-ldap server.
"""

import logging
import time

from flow import Flow

from src import utils
from src.db import backup
import flow_util


WAIT_SLEEP_SECS = 2
LOG = logging.getLogger("flow_setup")


class FlowSetupError(Exception):
    pass


def run(config):
    """Setups flow for the semaphor-ldap server."""
    flow = None
    try:
        flow = create_flow_object(config)
        device_created = setup_dma_account(flow, config)
        if device_created:
            wait_for_sync(flow)
        ldap_tid = setup_ldap_team(flow)
        backup_cid, log_cid = setup_ldap_channels(flow, ldap_tid)
        if device_created:
            restore_res = backup.restore(flow, ldap_tid, backup_cid)
            if not restore_res:
                raise Exception("db restore failed")
        return flow, {
            "ldap_team_id": ldap_tid,
            "backup_cid": backup_cid,
            "log_cid": log_cid,
        }
    except Exception as exception:
        if flow:
            flow.terminate()
        raise FlowSetupError(exception)
    return None


def create_flow_object(config):
    flow_config = {
        "host": config.get("flow-service-host"),
        "port": config.get("flow-service-port"),
        "use_tls": config.get("flow-service-use-tls"),
        "flowappglue": config.get("flowappglue"),
        "schema_dir": config.get("schema-dir"),
        "db_dir": utils.get_config_path(),
    }
    flow_args = {
        key: value for (key, value) in flow_config.items() \
        if value is not None
    }
    return Flow(**flow_args)


def setup_dma_account(flow, config):
    """Initializes Flow instance from config info.
    - If the account and device already exist, it will use them.
    - If the account exists, but there's no device, it creates a device.
    - If the account does not exist, it creates the account + device.
    Returns True if there was a device creation.
    """
    # An Account + Device may already be local
    # Try to start up first
    try:
        flow.start_up()
        LOG.debug(
            "local account '%s' started",
            flow.identifier()["username"],
        )
        return False
    except Flow.FlowError as start_up_err:
        LOG.debug("start_up failed: '%s'", str(start_up_err))

    # DMA account may already exist, but not locally.
    # Try creating a new device if 
    # username/password are provided in config
    flow_username = config.get("flow-username")
    flow_password = config.get("flow-password")
    if flow_username and flow_password:
        try:
            flow.create_device(
                username=flow_username,
                password=flow_password,
            )
            LOG.info(
                "Local Device for '%s' created",
                flow_username,
            )
            return True
        except Flow.FlowError as create_device_err:
            LOG.debug(
                "create_device failed: '%s'",
                str(create_device_err)
            )

    # Account may not exist, try to create account + device
    # for the Directory Management Account
    dmk_var = "directory-management-key"
    dmk = config.get(dmk_var)
    LOG.debug("%s", dmk)
    if not dmk:
        raise Exception("missing '%s'" % dmk_var)
    response = flow.create_dm_account(
        dmk=dmk,
    )
    ldap_tid = response["orgId"]
    print(
        "account user=%s with pass=%s for team=%s "
        "created successfully." % (
        response["username"], response["password"], ldap_tid,
    ))
    # Sending TJR to the LDAP team right away
    flow.new_org_join_request(ldap_tid)
    # Set bot profile
    set_dma_profile(flow)
    return False


def wait_for_member(flow):
    """Send the Team Join Request to the 
    LDAP team and wait for the notification.
    """
    LOG.debug("waiting for LDAP team join request approval")
    not_member = True
    while True:
        if flow_util.is_member_of_ldap_team(flow):
            break
        time.sleep(WAIT_SLEEP_SECS)
    LOG.debug("LDAP team join request approved")


def wait_for_admin(flow, tid):
    """Waits for the DMA to become admin of the LDAP team."""
    LOG.debug("waiting for DMA to become admin of LDAP team.")
    while True:
        if flow_util.is_team_admin(flow, tid):
            break
        time.sleep(WAIT_SLEEP_SECS)
    LOG.debug("DMA is admin of LDAP team")


def setup_ldap_team(flow):
    """Performs the setup (if not done yet)
    to become admin of the LDAP team.
    """
    # Check if member of LDAP team
    if not flow_util.is_member_of_ldap_team(flow):
        wait_for_member(flow)
    # Get LDAP team id if available
    ldap_tid = flow_util.get_ldap_team_id(flow)
    # Check if admin of LDAP team
    if not flow_util.is_team_admin(flow, ldap_tid):
        wait_for_admin(flow, ldap_tid)
    return ldap_tid


def setup_ldap_channels(flow, ldap_tid):
    backup_cid = create_backup_channel(flow, ldap_tid)
    log_cid = create_log_channel(flow, ldap_tid)
    return backup_cid, log_cid
    

def gen_backup_channel_name(flow):
    dma_username = flow.identifier()["username"]
    return "%s%s" % (
        dma_username, 
        utils.DMA_BACKUP_CHANNEL_SUFFIX_NAME,
    )


def create_backup_channel(flow, ldap_tid):
    # Check for existence
    account_id = flow.account_id()
    backup_channel_name = gen_backup_channel_name(flow)
    channels = flow.enumerate_channels(ldap_tid)
    for channel in channels:
        if channel["name"] == backup_channel_name:
            members = flow.enumerate_channel_member_history(channel["id"])
            if len(members) == 1 and \
               members[0]["accountId"] == account_id:
                backup_cid = channel["id"]
                break
    else:
        # Does not exist, create it
        backup_cid = flow.new_channel(
            ldap_tid, 
            backup_channel_name,
        )
    return backup_cid
            

def gen_log_channel_name(flow):
    dma_username = flow.identifier()["username"]
    return "%s%s" % (
        dma_username, 
        utils.DMA_LOG_CHANNEL_SUFFIX_NAME,
    )


def create_log_channel(flow, ldap_tid):
    # Check for existence
    account_id = flow.account_id()
    log_channel_name = gen_log_channel_name(flow)
    channels = flow.enumerate_channels(ldap_tid)
    for channel in channels:
        if channel["name"] == log_channel_name:
            members = flow.enumerate_channel_member_history(channel["id"])
            member = members[-1]
            if member["accountId"] == account_id and \
               member["state"] == "a":
                log_cid = channel["id"]
                break
    else:
        # Does not exist, create it
        log_cid = flow.new_channel(
            ldap_tid, 
            log_channel_name,
        )
    return log_cid


def wait_for_sync(flow):
    sync_done = { "value": False }
    def notify_event_handler(notif_type, notif_data):
        # EventCode: ReconnectingSyncStop is code 6
        if "EventCode" in notif_data and notif_data["EventCode"] == 6:
                sync_done["value"] = True
    flow.register_callback(
        Flow.NOTIFY_EVENT_NOTIFICATION,
        notify_event_handler,
    )
    LOG.info("waiting for flow local sync")
    while not sync_done["value"]:
        flow.process_one_notification(timeout_secs=30)
    LOG.info("flow local sync done")


def set_dma_profile(flow):
    # TODO update path
    # profile_image_file = "config/bot.jpg"
    # with open(profile_image_file, "r") as image_file:
    #    image_data = "data:image/jpg;base64,%s" % base64.b64encode(image_file.read())
    image_data = None
    content = flow.get_profile_item_json(
        display_name="Semaphor-LDAP Bot",
        biography="Semaphor-LDAP Bot Directory Management Account",
        photo=image_data,
    )
    flow.set_profile("profile", content) 
