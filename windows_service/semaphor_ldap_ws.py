"""
semaphor_ldap_ws.py

Run semaphor-ldap as a Windows Service

adapted from an ActiveState python recipe by Alexander Baker
http://code.activestate.com/recipes/576451-how-to-create-a-windows-service-in-python/
http://essiene.blogspot.com/2005/04/python-windows-services.html

Usage: 
$ python semaphor_ldap_ws.py {install,stop,remove,start}
"""

import os
import sys
import threading

import win32service
import win32serviceutil
import win32api
import win32con
import win32event
import servicemanager      
import win32evtlogutil

from src import semaphor_ldap


class SemaphorLDAPService(win32serviceutil.ServiceFramework):
   
    _svc_name_ = "Semaphor-LDAP"
    _svc_display_name_ = "Semaphor-LDAP"
    _svc_description_ = "SpiderOak Semaphor-LDAP"
         
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self._wait_stop = win32event.CreateEvent(None, 0, 0, None)           
        self._stop_server_event = threading.Event()
        self._semaphor_ldap_thread = threading.Thread(
			target=semaphor_ldap.run_server,
			args=(None, self._stop_server_event),
		)
        self._timeout = 60 * 1000

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self._wait_stop)                    
         
    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
	    	(self._svc_name_, ""),
        ) 
        servicemanager.LogInfoMsg("Semaphor-LDAP starting")
        self._semaphor_ldap_thread.start()

        while True:
            # Wait for service stop signal, 
            # if it timeouts, then loop again
            rc = win32event.WaitForSingleObject(
                self._wait_stop, 
                self._timeout,
            )
            # Check to see if self._wait_stop happened
            if rc == win32event.WAIT_OBJECT_0:
                # Stop signal encountered
                break
            else:
                if not self._semaphor_ldap_thread.is_alive():
                    servicemanager.LogInfoMsg(
                        "Semaphor-LDAP thread finished",
                    )
                    self._semaphor_ldap_thread = None
                    break

        if self._semaphor_ldap_thread is not None:
            servicemanager.LogInfoMsg("Semaphor-LDAP stopping")
            if self._semaphor_ldap_thread.is_alive():
                self._stop_server_event.set()
                self._semaphor_ldap_thread.join()
                servicemanager.LogInfoMsg(
                    "Semaphor-LDAP thread terminated",
                )


def CtrlHandler(ctrlType):
    return True


if __name__ == '__main__':   
    win32api.SetConsoleCtrlHandler(CtrlHandler, True)
    win32serviceutil.HandleCommandLine(SemaphorLDAPService)
