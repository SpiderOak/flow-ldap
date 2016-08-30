"""
flow_setup.py

Performs the flow setup process for semaphor-ldap server.
"""

import os
import logging
import time
import base64
import threading

from flow import Flow

from src import utils, app_platform
from src.db import backup
import flow_util


WAIT_SLEEP_SECS = 2
LOG = logging.getLogger("flow_setup")


class FlowSetupError(Exception):
    pass


def start_up(server):
    try:
        server.flow.start_up()
        LOG.debug(
            "local account '%s' started",
            server.flow.identifier()["username"],
        )
        setup_team_channels(server)
    except Flow.FlowError as start_up_err:
        LOG.debug("start_up failed: '%s'", str(start_up_err))


def create_device(server, flow_username, flow_password):
    if not (flow_username and flow_password):
        LOG.error("create_device: invalid args") 
        return False
    try:
        server.flow.create_device(
            username=flow_username,
            password=flow_password,
        )
        LOG.info(
            "Local Device for '%s' created",
            flow_username,
        )
        start_setup_team_channels(server, True)
        return True
    except Flow.FlowError as create_device_err:
        LOG.debug(
            "create_device failed: '%s'",
            str(create_device_err)
        )
        return False


def start_setup_team_channels(server, device_created=False):
    threading.Thread(
        target=setup_team_channels,
        args=(server, device_created,),
    ).start()


def setup_team_channels(server, device_created=False):
    try:
        if device_created:
            wait_for_sync(server.flow)
        ldap_tid = setup_ldap_team(server.flow)
        backup_cid, log_cid, test_cid = \
            setup_ldap_channels(server.flow, ldap_tid)
        if device_created:
            restore_res = backup.restore(
                server.flow, 
                ldap_tid, 
                backup_cid,
            )
            if not restore_res:
                raise Exception("db restore failed")
        # Add admins to log channel
        flow_util.add_admins_to_channel(
            server.flow, 
            ldap_tid,
            log_cid,
        )
        server.finalize_flow_config(
            ldap_tid, 
            backup_cid, 
            log_cid, 
            test_cid,
        )
    except Exception as exception:
        LOG.error("setup_team_channels failed: '%s'", str(exception))


def scan_prescribed_channels(server):
    """Performs a scan over the prescribed channels
    and adds remaining accounts to them.
    """
    LOG.debug("scan prescribed channels")
    prescribed_channel_ids = flow_util.get_prescribed_cids(
        server.flow, 
        server.ldap_team_id, 
    )
    if prescribed_channel_ids:
        flow_util.rescan_accounts_on_channels(
            server.flow, 
            server.db, 
            server.ldap_team_id,
            prescribed_channel_ids,
        )


def create_flow_object(config):
    flow_config = {
        "host": config.get("flow-service-host") or \
            utils.DEFAULT_FLOW_SERVICE_HOST,
        "port": config.get("flow-service-port") or \
            utils.DEFAULT_FLOW_SERVICE_PORT,
        "use_tls": config.get("flow-service-use-tls") or \
            utils.DEFAULT_FLOW_SERVICE_USE_TLS,
        "flowappglue": config.get("flowappglue") or \
            app_platform.get_default_flowappglue_path(),
        "schema_dir": config.get("schema-dir") or \
            app_platform.get_default_backend_schema_path(),
        "db_dir": app_platform.get_config_path(),
	"glue_out_filename": app_platform.get_glue_out_filename(),
    }
    flow_args = {
        key: value for (key, value) in flow_config.items() \
        if value is not None
    }
    flow = Flow(**flow_args)
    flow.set_api_timeout(utils.FLOW_API_TIMEOUT)
    return flow


def create_dma_account(server, dmk):
    assert(dmk)
    try:
        response = server.flow.create_dm_account(dmk=dmk)
        server.flow.new_org_join_request(response["orgId"])
        set_dma_profile(server.flow)
        start_setup_team_channels(server)
        return response
    except Flow.FlowError as flow_err:
        LOG.error("create_dma_account failed: '%s'", str(flow_err))
        raise


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
    backup_channel_name = gen_channel_name(
        flow,
        utils.DMA_BACKUP_CHANNEL_SUFFIX_NAME,
    )
    backup_cid = create_channel(
        flow, 
        ldap_tid, 
        backup_channel_name,
        private=True,
    )
    log_channel_name = gen_channel_name(
        flow,
        utils.DMA_LOG_CHANNEL_SUFFIX_NAME,
    )
    log_cid = create_channel(
        flow,
        ldap_tid,
        log_channel_name,
        private=False,
    )
    test_channel_name = gen_channel_name(
        flow,
        utils.DMA_TEST_CHANNEL_SUFFIX_NAME,
    )
    test_cid = create_channel(
        flow,
        ldap_tid,
        test_channel_name,
        private=False,
    )
    return backup_cid, log_cid, test_cid
    

def gen_channel_name(flow, suffix):
    dma_username = flow.identifier()["username"]
    return "%s%s" % (
        dma_username,
        suffix,
    )


def create_channel(flow, tid, channel_name, private):
    account_id = flow.account_id()
    channels = flow.enumerate_channels(tid)
    # Check for existence
    for channel in channels:
        if channel["name"] == channel_name:
            members = flow.enumerate_channel_member_history(channel["id"])
            member = members[-1]
            if member["accountId"] == account_id and member["state"] == "a":
                if not (private and len(members) != 1):
                    cid = channel["id"]
                    break
    else:
        # Does not exist, create it
        cid = flow.new_channel(
            tid, 
            channel_name,
        )
    return cid
            

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
    profile_img_filename = os.path.join(
        app_platform.get_default_img_path(),
        "bot.jpg",
    )
    image_data = None
    if os.path.isfile(profile_img_filename):
        with open(profile_img_filename, "rb") as image_file:
	    image_raw_data = image_file.read()
        image_data = "data:image/jpeg;base64,%s" % ( 
	    base64.b64encode(image_raw_data),
	)
    content = flow.get_profile_item_json(
        display_name="Semaphor-LDAP Bot",
        biography=\
            "Semaphor-LDAP Bot Directory Management Account",
        photo=image_data,
    )
    flow.set_profile("profile", content) 
