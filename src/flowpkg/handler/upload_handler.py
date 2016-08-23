"""
upload_handler.py

"""

import logging

from flow import Flow


LOG = logging.getLogger("upload_handler")


class UploadHandler(object):

    def __init__(self):
        self.notif_types = [
            Flow.UPLOAD_COMPLETE_NOTIFICATION,
            Flow.UPLOAD_ERROR_NOTIFICATION,
        ]

    def callback(self, notif_type, notif_data):
        if notif_type == Flow.UPLOAD_ERROR_NOTIFICATION:
            LOG.error("upload failed: '%s'", notif_data["err"])
        elif notif_type == Flow.UPLOAD_COMPLETE_NOTIFICATION:
            LOG.debug("upload completed")
