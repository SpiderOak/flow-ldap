"""
notify_handler.py

Processes the notify-event notifications.
It currently handles the auto-update notifications.
"""

import logging

from flow import Flow
import src.utils


LOG = logging.getLogger("notify_handler")


class NotifyEventHandler(object):
    """Processes the notify-event notifications.
    It checks for new auto-updates. If a new auto-update
    is downloaded, then the application is restarted.
    """

    def __init__(self):
        self.notif_types = [Flow.NOTIFY_EVENT_NOTIFICATION]

    def callback(self, _notif_type, notif_data):
        """Callback to execute on channel-member-event notification."""
        event_code = notif_data.get("EventCode")
        text = notif_data.get("Text")
        if event_code == 24:
            LOG.info("auto-update available: %s", text)
        elif event_code == 25:
            LOG.error("auto-update error: %s", text)
        elif event_code == 27:
            LOG.info("auto-update downloaded: %s", text)
            src.utils.terminate_service_app()
