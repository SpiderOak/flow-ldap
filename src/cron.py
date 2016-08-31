"""
cron.py

Runs the scheduled tasks.
"""

import time
import logging
import threading

import schedule


LOG = logging.getLogger("cron")


class Cron(threading.Thread):
    """Runs the LDAP sync operation."""

    def __init__(self):
        super(Cron, self).__init__()
        self.loop_schedule = threading.Event()
        self.loop_schedule.set()

    def stop(self):
        """Finishes the execution of the LDAP sync thread."""
        self.loop_schedule.clear()

    def update_task_frequency(self, minutes, task_function):
        """Sets a task to run every 'minutes' minutes.
        Arguments:
        - minutes : int, number of minutes between the given task.
        If minutes=0 then the task is disabled.
        - task_func : function object with the operation to run.
        """
        LOG.debug(
            "updating task frequency to %d minutes for '%s()'",
            minutes,
            task_function.__name__,
        )
        # If existing job, then cancel it
        jobs = [job for job in schedule.jobs if job.job_func.func == task_function]
        if len(jobs) == 1:
            schedule.cancel_job(jobs[0])
        # Schedule the job
        if minutes:
            schedule.every(minutes).minutes.do(task_function)

    def run(self):
        """Runs the schedule loop."""
        LOG.debug("cron thread started")
        while self.loop_schedule.is_set():
            try:
                schedule.run_pending()
            except Exception as exception:
                LOG.error("cron job failed: %s", exception)
            time.sleep(1)
        LOG.debug("cron thread finished")
