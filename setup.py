import sys
import src.utils
from setuptools import setup, find_packages
try:
    from pip.req import parse_requirements
except ImportError:
    print("The 'pip' package is needed for the setup")
    exit(1)

BINARY_NAME = "semaphor-ldap"

reqs = parse_requirements("requirements/requirements.txt", session=False)
install_requires = [str(ir.req) for ir in reqs]


def set_win32_options(options):
    try:
        import py2exe
    except ImportError:
        print("The 'py2exe' package is needed for the setup")
        exit(1)
    options.update(
        console=[{
            "script": "src/semaphor_ldap.py",
            "dest_base": BINARY_NAME,
        }],
        options={
            "py2exe": {
                "dll_excludes": "CRYPT32.DLL",
            },
        },
    )

setup_options = dict(
    name="semaphor-ldap",
    version=src.utils.VERSION,
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "%s = src.semaphor_ldap:main" % BINARY_NAME,
        ],
    },
    install_requires=install_requires,
    keywords=["spideroak", "semaphor", "ldap"],
    author="SpiderOak Inc.",
    author_email="support@spideroak.com",
    description="semaphor-ldap runs on "
    "Customer Infrastructure "
    "enabling the use of Semaphor with "
    "Customer LDAP credentials.",
)

if "py2exe" in sys.argv:
    set_win32_options(setup_options)

print("Run setup")
setup(**setup_options)
