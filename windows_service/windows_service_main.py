"""
windows_service_main.py

Run semaphor-ldap as a Windows Service

adapted from an ActiveState python recipe by Alexander Baker
http://code.activestate.com/recipes/576451-how-to-create-a-windows-service-in-python/
http://essiene.blogspot.com/2005/04/python-windows-services.html

Usage: 
$ python aservice.py install
$ python aservice.py start
$ python aservice.py stop
$ python aservice.py remove
"""

import win32service
import win32serviceutil
import win32api
import win32con
import win32event
import servicemanager      
import win32evtlogutil

import os
import os.path
import subprocess
import sys

class SemaphorLDAPService(win32serviceutil.ServiceFramework):
   
    _svc_name_ = "Semaphor-LDAP"
    _svc_display_name_ = "Semaphor-LDAP"
    _svc_description_ = "SpiderOak Semaphor-LDAP"
         
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self._wait_stop = win32event.CreateEvent(None, 0, 0, None)           
        executable_dir = os.path.dirname(sys.executable)
        spider_executable_path = os.path.join(
            executable_dir, "semaphor-ldap.exe",
        )
        self._semaphor_ldap_args = [spider_executable_path, "server",] 
        self._timeout = 60 * 1000
        self._semaphor_ldap_process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self._wait_stop)                    
         
    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,(self._svc_name_, ""),
        ) 
        servicemanager.LogInfoMsg("Semaphor-LDAP starting %s" % (
            self._semaphor_ldap_args
        ))
        self._semaphor_ldap_process = subprocess.Popen(self._semaphor_ldap_args)

        while True:
            # Wait for service stop signal, if I timeout, loop again
            rc = win32event.WaitForSingleObject(self._wait_stop, self._timeout)
            # Check to see if self._wait_stop happened
            if rc == win32event.WAIT_OBJECT_0:
                # Stop signal encountered
                break
            else:
                if self._semaphor_ldap_process is None:
                    servicemanager.LogInfoMsg(
                        "Semaphor-LDAP process is None"
                    )
                    break

                self._semaphor_ldap_process.poll()
                if self._semaphor_ldap_process.returncode is not None:
                    servicemanager.LogInfoMsg(
                        "Semaphor-LDAP terminated: %s" % (
                            self._semaphor_ldap_process.returncode,
                        ),
                    )
                    self._semaphor_ldap_process = None

        servicemanager.LogInfoMsg("Semaphor-LDAP stopping")
        if self._semaphor_ldap_process is not None:
            self._semaphor_ldap_process.terminate()
            self._semaphor_ldap_process.wait()
            servicemanager.LogInfoMsg(
                "Semaphor-LDAP return code: %s" % (
                    self._semaphor_ldap_process.returncode,
                ),
            )


def CtrlHandler(ctrlType):
    return True


if __name__ == '__main__':   
    win32api.SetConsoleCtrlHandler(CtrlHandler, True)
    win32serviceutil.HandleCommandLine(SemaphorLDAPService)
