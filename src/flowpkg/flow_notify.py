"""
flow_notify.py

Processes notifications coming from the flow service.
"""

import time
import threading
import logging


MUST_UPGRADE_ERROR_LATENCY = 60 * 60 * 6  # 6 hours
LOG = logging.getLogger("flow_notify")


class FlowNotify(threading.Thread):
    """Thread class to process incoming server notifications."""

    def __init__(self, dma_manager):
        super(FlowNotify, self).__init__()
        self.dma_manager = dma_manager
        self.loop_listener = threading.Event()
        self.loop_listener.set()
        self.last_must_upgrade_notify = 0.0

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

    def log_notify_error(self, error):
        """Logs notification errors to the ERROR log."""
        if "Connection aborted" in error:
            # No need to log these
            return
        if "Must Upgrade" in error:
            now = time.time()
            latency = abs(now - self.last_must_upgrade_notify)
            if latency < MUST_UPGRADE_ERROR_LATENCY:
                return
            self.last_must_upgrade_notify = now
        LOG.error("notification error: '%s'", error)

    def run(self):
        """Run the FlowNotify thread."""
        LOG.info("flow notify thread started")
        LOG.info("wait flow setup")
        self.dma_manager.ready.wait()
        if not self.loop_listener.is_set():
            return
        LOG.info("flow ready, start notification listener")
        while self.loop_listener.is_set():
            self.dma_manager.flow.process_one_notification(timeout_secs=0.05)
            error = self.dma_manager.flow.get_notification_error(
                timeout_secs=0.05)
            if error:
                self.log_notify_error(error)
        LOG.info("flow notify thread finished")
