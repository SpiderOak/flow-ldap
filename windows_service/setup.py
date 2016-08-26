"""
setup.py

Setup for Semaphor-LDAP Windows Sevice.
"""
import sys
        
from distutils.core import setup
import os
import py2exe
import glob
import shutil

DESCRIPTION = 'Semaphor-LDAP Windows Service'
NAME = 'Semaphor-LDAP'

class Target:
    def __init__(self,**kw):
        self.__dict__.update(kw)
        self.version        = "1.00.00"
        self.company_name   = "spideroak.com"
        self.copyright      = "(c) 2016, SpiderOak Inc."
        self.name           = NAME
        self.description    = DESCRIPTION
    
semaphor_windows_service = Target(
    description = DESCRIPTION,
    modules = ['windows_service_main'],
    cmdline_style='pywin32',
)

setup(
    service = [semaphor_windows_service],
    zipfile='service_runner/shared.zip',
    options = {
        "py2exe":{  "packages" : "encodings",
                    "includes" : \
                        "win32com, win32service, win32serviceutil, win32event",
                    "bundle_files" : \
                        3,
                    "dll_excludes" : \
                        "POWRPROF.dll, \
                        API-MS-Win-Core-LocalRegistry-L1-1-0.dll, \
                        API-MS-Win-Core-ProcessThreads-L1-1-0.dll, \
                        API-MS-Win-Security-Base-L1-1-0.dll",
        },
    },
) 
