"""
upload_handler.py

Process upload-error and upload-complete notifications.
"""

import logging

from flow import Flow


LOG = logging.getLogger("upload_handler")


class UploadHandler(object):
    """Processes upload-error and upload-complete notifications.
    Used for notifying the upload result to the log.
    """

    def __init__(self):
        self.notif_types = [
            Flow.UPLOAD_COMPLETE_NOTIFICATION,
            Flow.UPLOAD_ERROR_NOTIFICATION,
        ]

    def callback(self, notif_type, notif_data):
        """Callback to notify the upload result to the log."""
        if notif_type == Flow.UPLOAD_ERROR_NOTIFICATION:
            LOG.error("upload failed: '%s'", notif_data["err"])
        elif notif_type == Flow.UPLOAD_COMPLETE_NOTIFICATION:
            LOG.info("upload completed")
