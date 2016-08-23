"""
flow_notify.py

Processes notifications coming from the flow service.
"""

import threading
import logging

from flow import Flow


LOG = logging.getLogger("flow_notify")


class FlowNotify(threading.Thread):

    def __init__(self, server):
        super(FlowNotify, self).__init__()
        self.flow = server.flow
        self.loop_listener = threading.Event()
        self.loop_listener.set()

    def add_handler(self, handler):
        for notif_type in handler.notif_types:
            self.flow.register_callback(
                notif_type,
                handler.callback,
            )

    def remove_handler(self, handler):
        for notif_type in handler.notif_types:
            self.flow.unregister_callback(
                handler.notif_type,
            )

    def stop(self):
        self.loop_listener.clear()

    def run(self):
        LOG.debug("flow notify thread started")
        while self.loop_listener.is_set():
            self.flow.process_one_notification(timeout_secs=0.05)
            error = self.flow.get_notification_error(timeout_secs=0.05)
            if error and "Connection aborted" not in error:
                LOG.error("notification error: '%s'", error)
        LOG.debug("flow notify thread finished")
