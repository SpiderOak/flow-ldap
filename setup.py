from setuptools import setup

setup(name = "semaphor-ldap",
      version = "0.1",
      packages = [ 'src' ],
      entry_points = {
        "console_scripts": [
        "semaphor-ldap=src.semaphor_ldap:main",
        ],
      },
      # TODO: add "flow-python", "ldap-reader" as soon as
      # they are available at PyPi
      install_requires = [ "schedule" ],  
      keywords = [ "spideroak", "semaphor", "ldap" ],
      author = "Lucas Manuel Rodriguez",
      author_email = "lucas@spideroak-inc.com",
      description = "semaphor-ldap runs on " \
                    "Customer Infrastructure " \
                    "enabling the use of Semaphor with " \
                    "Customer LDAP credentials.",
)
