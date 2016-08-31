"""
dma_manager.py

Directory Management Account Manager.
"""

import os
import logging
import time
import base64
import threading

from flow import Flow

from src import utils, app_platform
from src.db import backup
from src.log import app_log
from src.flowpkg import flow_util
from src.flowpkg.flow_notify import FlowNotify
from src.flowpkg.handler import (
    LDAPBindRequestHandler,
    ChannelMemberEventHandler,
    UploadHandler,
    TeamMemberEventHandler,
)
from src.log.flow_log_channel_handler import FlowRemoteLogger

WAIT_SLEEP_SECS = 2
LOG = logging.getLogger("flow_manager")


class DMAManager(object):

    def __init__(self, server):
        self.config = server.config
        self.db = server.db
        self.ldap_factory = server.ldap_factory
        self.cron = server.cron
        self.flow = None
        self.flow_notify = None
        self.flow_remote_logger = None
        self.ldap_team_id = ""
        self.backup_cid = ""
        self.log_cid = ""
        self.test_cid = ""
        self.ready = threading.Event()
        self.threads_running = False

        self.init_flow()
        self.init_remote_logger()
        self.init_flow_notify()
        self.init_handlers()

    def set_db_backup_mins_from_config(self):
        minutes = int(self.config.get("db-backup-minutes"))
        LOG.debug("updating backup cron to %d minutes", minutes)
        self.cron.update_task_frequency(minutes, self.run_backup)

    def schedule_backup(self):
        self.config.register_callback(
            ["db-backup-minutes"],
            self.set_db_backup_mins_from_config,
        )
        self.set_db_backup_mins_from_config()

    def init_flow(self):
        LOG.debug("initializing the flow service")
        self.flow = flow_util.create_flow_object(
            self.config,
        )
        self.start_up()

    def init_remote_logger(self):
        LOG.debug("initializing the remote flow logger")
        self.flow_remote_logger = FlowRemoteLogger(self)
        app_log.configure_flow_log(self.flow_remote_logger)

    def init_flow_notify(self):
        LOG.debug("initializing the flow notify thread")
        self.flow_notify = FlowNotify(self)

    def init_handlers(self):
        LOG.debug("initializing flow notify handlers")
        self.ldap_bind_request_handler = LDAPBindRequestHandler(self)
        self.cme_handler = ChannelMemberEventHandler(self)
        self.upload_handler = UploadHandler()
        self.tme_handler = TeamMemberEventHandler(self)
        self.flow_notify.add_handler(self.ldap_bind_request_handler)
        self.flow_notify.add_handler(self.cme_handler)
        self.flow_notify.add_handler(self.upload_handler)
        self.flow_notify.add_handler(self.tme_handler)

    def start(self):
        LOG.debug("starting flow threads")
        self.flow_notify.start()
        self.flow_remote_logger.start()
        self.threads_running = True

    def stop(self):
        LOG.debug("stopping the dma manager")
        if self.threads_running:
            self.flow_notify.stop()
            self.flow_remote_logger.stop()
            self.ready.set()
            self.flow_notify.join()
            self.flow_remote_logger.join()
        if self.flow:
            self.flow.terminate()

    def finalize_flow_config(self):
        # Add admins to log channels
        flow_util.add_admins_to_channel(
            self.flow,
            self.ldap_team_id,
            self.log_cid,
        )
        # Perform scan to add db accounts (if any) to prescribed channels
        self.scan_prescribed_channels()
        self.ready.set()
        self.schedule_backup()

    def check_flow_connection(self):
        if not self.ready.is_set():
            raise Exception("DMA is not configured yet")
        flow_util.check_flow_connection(
            self.flow,
            self.ldap_team_id,
            self.test_cid,
        )

    def get_dma_fingerprint(self):
        if not self.ready.is_set():
            raise Exception("DMA is not configured yet")
        return self.flow.keyring_fingerprint()

    def start_up(self):
        LOG.debug("starting up dma account")
        try:
            self.flow.start_up()
            LOG.debug(
                "local account '%s' started",
                self.flow.identifier()["username"],
            )
            self.setup_team_channels()
        except Flow.FlowError as start_up_err:
            LOG.debug("start_up failed: '%s'", str(start_up_err))

    def create_device(self, flow_username, flow_password):
        assert(flow_username)
        assert(flow_password)
        LOG.debug("creating dma device")
        try:
            self.flow.create_device(
                username=flow_username,
                password=flow_password,
            )
            LOG.info(
                "Local Device for '%s' created",
                flow_username,
            )
            self.start_setup_team_channels(True)
        except Flow.FlowError as create_device_err:
            LOG.error(
                "create_device failed: '%s'",
                str(create_device_err)
            )
            raise

    def start_setup_team_channels(self, device_created=False):
        threading.Thread(
            target=self.setup_team_channels,
            args=(device_created,),
        ).start()

    def setup_team_channels(self, device_created=False):
        LOG.debug("setting up ldap team and channels")
        try:
            if device_created:
                self.wait_for_sync()
            self.setup_ldap_team()
            self.setup_ldap_channels()
            if device_created:
                backup.restore(
                    self.flow,
                    self.ldap_team_id,
                    self.backup_cid,
                )
            self.finalize_flow_config()
        except Exception as exception:
            LOG.error("setup_team_channels failed: '%s'", str(exception))

    def scan_prescribed_channels(self):
        """Performs a scan over the prescribed channels
        and adds remaining accounts to them.
        """
        LOG.debug("scan prescribed channels")
        prescribed_channel_ids = flow_util.get_prescribed_cids(
            self.flow,
            self.ldap_team_id,
        )
        flow_util.rescan_accounts_on_channels(
            self.flow,
            self.db,
            self.ldap_team_id,
            prescribed_channel_ids,
        )

    def create_dma_account(self, dmk):
        assert(dmk)
        try:
            LOG.debug("creating dma")
            response = self.flow.create_dm_account(dmk=dmk)
            self.flow.new_org_join_request(response["orgId"])
            self.set_dma_profile()
            self.start_setup_team_channels()
            return response
        except Flow.FlowError as flow_err:
            LOG.error("create_dma_account failed: '%s'", str(flow_err))
            raise

    def wait_for_member(self):
        """Send the Team Join Request to the
        LDAP team and wait for the notification.
        """
        LOG.debug("waiting for LDAP team join request approval")
        while True:
            if flow_util.is_member_of_ldap_team(self.flow):
                break
            time.sleep(WAIT_SLEEP_SECS)
        LOG.debug("LDAP team join request approved")

    def wait_for_admin(self, tid):
        """Waits for the DMA to become admin of the LDAP team."""
        LOG.debug("waiting for DMA to become admin of LDAP team.")
        while True:
            if flow_util.is_team_admin(self.flow, tid):
                break
            time.sleep(WAIT_SLEEP_SECS)
        LOG.debug("DMA is admin of LDAP team")

    def setup_ldap_team(self):
        """Performs the setup (if not done yet)
        to become admin of the LDAP team.
        """
        # Check if member of LDAP team
        if not flow_util.is_member_of_ldap_team(self.flow):
            self.wait_for_member()
        # Get LDAP team id if available
        ldap_team_id = flow_util.get_ldap_team_id(self.flow)
        # Check if admin of LDAP team
        if not flow_util.is_team_admin(self.flow, ldap_team_id):
            self.wait_for_admin(ldap_team_id)
        self.ldap_team_id = ldap_team_id

    def setup_ldap_channels(self):
        backup_channel_name = self.gen_channel_name(
            utils.DMA_BACKUP_CHANNEL_SUFFIX_NAME,
        )
        LOG.debug("creating/getting backup channel")
        self.backup_cid, _ = self.get_channel(
            self.ldap_team_id,
            backup_channel_name,
            private=True,
        )
        log_channel_name = self.gen_channel_name(
            utils.DMA_LOG_CHANNEL_SUFFIX_NAME,
        )
        LOG.debug("creating/getting log channel")
        self.log_cid, created = self.get_channel(
            self.ldap_team_id,
            log_channel_name,
            private=False,
        )
        if created:
            self.send_fingerprint()
        test_channel_name = self.gen_channel_name(
            utils.DMA_TEST_CHANNEL_SUFFIX_NAME,
        )
        LOG.debug("creating/getting test channel")
        self.test_cid, _ = self.get_channel(
            self.ldap_team_id,
            test_channel_name,
            private=False,
        )

    def gen_channel_name(self, suffix):
        dma_username = self.flow.identifier()["username"]
        return "%s%s" % (
            dma_username,
            suffix,
        )

    def get_channel(self, tid, channel_name, private):
        account_id = self.flow.account_id()
        channels = self.flow.enumerate_channels(tid)
        # Check for existence
        for channel in channels:
            if channel["name"] == channel_name:
                members = self.flow.enumerate_channel_member_history(
                    channel["id"],
                )
                member = members[-1]
                if member["accountId"] == account_id and member[
                        "state"] == "a":
                    if not (private and len(members) == 1):
                        cid = channel["id"]
                        created = False
                        break
        else:
            # Does not exist, create it
            cid = self.flow.new_channel(
                tid,
                channel_name,
            )
            created = True
        return cid, created

    def wait_for_sync(self):
        sync_done = {"value": False}

        def notify_event_handler(_notif_type, notif_data):
            # EventCode: ReconnectingSyncStop is code 6
            if "EventCode" in notif_data and notif_data["EventCode"] == 6:
                sync_done["value"] = True
        self.flow.register_callback(
            Flow.NOTIFY_EVENT_NOTIFICATION,
            notify_event_handler,
        )
        LOG.info("waiting for flow local sync")
        while not sync_done["value"]:
            self.flow.process_one_notification(timeout_secs=30)
        LOG.info("flow local sync done")

    def set_dma_profile(self):
        LOG.debug("setting dma profile")
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
        content = self.flow.get_profile_item_json(
            display_name="Semaphor-LDAP Bot",
            biography="Semaphor-LDAP Bot Directory Management Account",
            photo=image_data,
        )
        self.flow.set_profile("profile", content)

    def run_backup(self):
        if not self.ready.is_set():
            LOG.debug("skipping local db backup, flow not ready")
            return
        LOG.debug("running local db backup")
        backup.run(
            self.db,
            self.flow,
            self.ldap_team_id,
            self.backup_cid,
        )

    def send_fingerprint(self):
        fpr = self.flow.keyring_fingerprint()
        self.flow.send_message(
            self.ldap_team_id,
            self.log_cid,
            "Semaphor Sign-In URI: %s" % (
                utils.URI_FINGERPRINT % {"fp": fpr}
            ),
        )
