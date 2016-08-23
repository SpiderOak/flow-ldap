"""
backup.py

Performs a local DB backup on a Semaphor channel.
"""

import logging
from shutil import copyfile

from flow import Flow

from src import utils


LOG = logging.getLogger("backup")


def run(db, flow, ldap_tid, backup_cid):
    """Perform the DB backup and save it as attachment."""
    if not (flow and ldap_tid and backup_cid):
        return
    # run db back up
    backup_filename = db.run_backup()
    try:
        LOG.debug("uploading db")
        # upload backup as attachment
        aid = flow.new_attachment(
            ldap_tid,
            backup_filename,
        ) 
        # send the attachment to the backup channel
        flow.send_message(
            ldap_tid,
            backup_cid,
            backup_filename,
            [aid],
        )
    except Flow.FlowError as flow_err:
        LOG.error("backup failed: %s", str(flow_err))


def restore(flow, ldap_tid, backup_cid):
    """If available, restore the local DB from the backup channel."""
    assert(flow)
    assert(ldap_tid)
    assert(backup_cid)
    msgs = flow.enumerate_messages(ldap_tid, backup_cid)
    if not msgs:
        # no backup available
        LOG.debug("no db backup available")
        return True
    last_backup_msg = msgs[0]
    aids = last_backup_msg["attachment"]
    # we only store messages with attachments on the backup channel
    assert(aids)
    aid = aids[0]
    LOG.info("downloading last db backup")
    flow.start_attachment_download(
        aid,
        ldap_tid,
        backup_cid,
        last_backup_msg["id"],
    )
    # wait until download is done
    download_error = { "value": None }
    def download_complete_handler(notif_type, notif_data):
        pass
    flow.register_callback(
        Flow.DOWNLOAD_COMPLETE_NOTIFICATION,
        download_complete_handler,
    )
    def download_error_handler(notif_type, notif_data):
        download_error["value"] = notif_data["err"]
    flow.register_callback(
        Flow.DOWNLOAD_ERROR_NOTIFICATION,
        process_error,
    )
    flow.process_one_notification(timeout_secs=None)
    download_error_value = download_error["value"]
    flow.unregister_callback(Flow.DOWNLOAD_COMPLETE_NOTIFICATION)
    flow.unregister_callback(Flow.DOWNLOAD_ERROR_NOTIFICATION)
    if download_error_value:
        LOG.error("db backup download failed: %s", download_error_value)
        return False
    LOG.info("last db backup downloaded successfully")
    backup_path = flow.stored_attachment_path(ldap_tid, aid)
    assert(backup_path)
    local_db_path = utils.local_db_path(flow.identifier()["username"])
    copyfile(backup_path, local_db_path)
    LOG.info("last db backup restored successfully")
    return True
