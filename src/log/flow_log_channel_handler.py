"""
flow_log_channel_handler.py

Logs messages to a Semaphor channel.
"""

import logging
import threading
import Queue


class NotMemberLogChannelError(Exception):
    """Excepion raised when the DMA is not a member of the LOG channel."""
    pass


class FlowLogChannelHandler(logging.Handler):
    """Log handler to send records to a given flow remote logger.
    We have to queue the record because we cannot log messages
    with ~2 seconds of latency.
    """

    def __init__(self, flow_remote_logger):
        super(FlowLogChannelHandler, self).__init__()
        self.flow_remote_logger = flow_remote_logger

    def emit(self, record):
        """It queues the given record to the remote logger."""
        record_str = self.format(record)
        try:
            self.flow_remote_logger.queue_message(record_str)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


class FlowRemoteLogger(threading.Thread):
    """Thread class to send log messages to the LOG channel.
    It reads the messages from an internal queue.
    """

    def __init__(self, dma_manager):
        super(FlowRemoteLogger, self).__init__()
        self.dma_manager = dma_manager
        self.flow = dma_manager.flow
        self.loop_logger = threading.Event()
        self.loop_logger.set()
        self.log_queue = Queue.Queue()
        self.MAX_Q_SIZE = 100

    def check_member(self, cid):
        """Checks whether the account is member of the given cid."""
        members = [
            member["accountId"]
            for member in
            self.flow.enumerate_channel_members(cid)
        ]
        return self.flow.account_id() in members

    def queue_message(self, message):
        """Queues the given message to the internal queue."""
        if self.log_queue.qsize() >= self.MAX_Q_SIZE:
            return
        self.log_queue.put(message)

    def stop(self):
        """Finishes the execution of the LDAP sync thread."""
        self.loop_logger.clear()

    def run(self):
        """Runs the remote logger thread.
        It gets messages from the queue and sends them to the LOG channel."""
        logger = logging.getLogger("flow_remote_logger")
        logger.debug("flow remote logger thread started")
        logger.debug("wait flow setup")
        self.dma_manager.ready.wait()
        if not self.loop_logger.is_set():
            return
        tid = self.dma_manager.ldap_team_id
        cid = self.dma_manager.log_cid
        if not self.check_member(cid):
            raise NotMemberLogChannelError(
                "Not member of the specified channel",
            )
        logger.debug("flow ready start loop")
        while self.loop_logger.is_set():
            try:
                message = self.log_queue.get(block=True, timeout=0.25)
            except Queue.Empty:
                continue
            try:
                self.flow.send_message(
                    tid,
                    cid,
                    message,
                    timeout=10,
                )
            except Exception:
                logger.debug("send_message to log channel failed")
        logger.debug("flow remote logger thread finished")
