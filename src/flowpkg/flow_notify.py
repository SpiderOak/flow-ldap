"""
flow_notify.py

Processes notifications coming from the flow service.
"""

import threading
import logging


LOG = logging.getLogger("flow_notify")


class FlowNotify(threading.Thread):
    """Thread class to process incoming server notifications."""

    def __init__(self, dma_manager):
        super(FlowNotify, self).__init__()
        self.dma_manager = dma_manager
        self.loop_listener = threading.Event()
        self.loop_listener.set()

    def add_handler(self, handler):
        """Asociate the given handler to a certain type of notifications."""
        for notif_type in handler.notif_types:
            self.dma_manager.flow.register_callback(
                notif_type,
                handler.callback,
            )

    def stop(self):
        """Terminate the FlowNotify thread."""
        self.loop_listener.clear()

    def run(self):
        """Run the FlowNotify thread."""
        LOG.debug("flow notify thread started")
        LOG.debug("wait flow setup")
        self.dma_manager.ready.wait()
        if not self.loop_listener.is_set():
            return
        LOG.debug("flow ready, start notification listener")
        while self.loop_listener.is_set():
            self.dma_manager.flow.process_one_notification(timeout_secs=0.05)
            error = self.dma_manager.flow.get_notification_error(
                timeout_secs=0.05)
            if error and "Connection aborted" not in error:
                LOG.error("notification error: '%s'", error)
        LOG.debug("flow notify thread finished")
