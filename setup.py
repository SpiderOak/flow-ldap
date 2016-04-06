from setuptools import setup

setup(name = "flow-ldap",
      version = "0.1",
      packages = [ 'src' ],
      entry_points = {
        "console_scripts": [
        "flow-ldap=src.flow_ldap:main",
        ],
      },
      # TODO: add "flow-python", "ldap-reader" as soon as
      # they are available at PyPi
      install_requires = [ "schedule" ],  
      keywords = [ "spideroak", "flow", "semaphor", "ldap" ],
      author = "Lucas Manuel Rodriguez",
      author_email = "lucas@spideroak-inc.com",
      description = "flow-ldap runs on " \
                    "Customer Infrastructure " \
                    "enabling the use of Semaphor with " \
                    "Customer LDAP credentials.",
)
