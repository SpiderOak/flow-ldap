import src.utils
from setuptools import setup

import py2exe

setup(name = "semaphor-ldap",
      version = src.utils.VERSION,
      packages = [ "src", "src/log", "src/db", "src/sync", "src/flowpkg", "src/flowpkg/handler" ],
      entry_points = {
        "console_scripts": [
        "semaphor-ldap=src.semaphor_ldap:main",
        ],
      },
      install_requires = [ "schedule" ],  
      keywords = [ "spideroak", "semaphor", "ldap" ],
      author = "Lucas Manuel Rodriguez",
      author_email = "lucas@spideroak-inc.com",
      description = "semaphor-ldap runs on " \
                    "Customer Infrastructure " \
                    "enabling the use of Semaphor with " \
                    "Customer LDAP credentials.",
      console = [{
            "script": "src/semaphor_ldap.py",
      }],
)
