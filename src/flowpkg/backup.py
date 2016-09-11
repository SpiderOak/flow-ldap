"""
backup.py

Performs a local DB backup on a private Semaphor channel.
"""

import logging
from shutil import copyfile

from flow import Flow

from src import app_platform


LOG = logging.getLogger("backup")


def run(db, flow, ldap_tid, backup_cid):
    """Perform the DB backup and upload it as an attachment
    on the provided 'backup_cid' private channel.
    """
    assert(flow)
    assert(ldap_tid)
    assert(backup_cid)
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
    """If available, restore the local DB from the
    backup private channel.
    """
    assert(flow)
    assert(ldap_tid)
    assert(backup_cid)
    msgs = flow.enumerate_messages(ldap_tid, backup_cid)
    if not msgs:
        # no backup available
        LOG.debug("no db backup available")
        return
    last_backup_msg = msgs[0]
    attachments = last_backup_msg["attachments"]
    # we only store messages with attachments on the backup channel
    assert(attachments)
    aid = attachments[0]["id"]
    LOG.info("downloading last db backup")
    flow.start_attachment_download(
        aid,
        ldap_tid,
        backup_cid,
        last_backup_msg["id"],
    )
    # wait until download is done
    download_error = {"value": None}

    def download_complete_handler(_notif_type, _notif_data):
        pass
    flow.register_callback(
        Flow.DOWNLOAD_COMPLETE_NOTIFICATION,
        download_complete_handler,
    )

    def download_error_handler(_notif_type, notif_data):
        download_error["value"] = notif_data["err"]
    flow.register_callback(
        Flow.DOWNLOAD_ERROR_NOTIFICATION,
        download_error_handler,
    )
    flow.process_one_notification(timeout_secs=None)
    download_error_value = download_error["value"]
    flow.unregister_callback(Flow.DOWNLOAD_COMPLETE_NOTIFICATION)
    flow.unregister_callback(Flow.DOWNLOAD_ERROR_NOTIFICATION)
    if download_error_value:
        LOG.error("db backup download failed: %s", download_error_value)
        raise Exception("backup download failed")
    LOG.info("last db backup downloaded successfully")
    backup_path = flow.stored_attachment_path(ldap_tid, aid)
    assert(backup_path)
    local_db_filename = app_platform.local_db_path()
    copyfile(backup_path, local_db_filename)
    LOG.info("last db backup restored successfully")
