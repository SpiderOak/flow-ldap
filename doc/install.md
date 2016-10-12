# Semaphor-LDAP Installation Guide

# Developer Install

Setup your virtualenv:
```bash
$ mkdir venv
$ virtualenv venv
$ . venv/bin/activate
```
Install SpiderOak dependencies (this will be improved once we move `flow-python` and `ldap-reader` to PyPi)
```bash
# Install flow-python
$ git clone git@github.com:SpiderOak/flow-python.git
$ cd flow-python
$ python setup.py install

# Install ldap-reader
$ git clone git@github.com:SpiderOak/ldap-reader.git
$ cd ldap-reader
$ python setup.py install

```
Install `semaphor-ldap`:
```bash
$ git clone git@github.com:SpiderOak/flow-ldap.git
$ cd flow-ldap
$ python setup.py install  # This will also install dependencies
# Test installation 
$ semaphor-ldap --help
```

# Windows Install

For Windows we provide a separate setup to generate the semaphor-ldap server as a Windows Service.
We use py2exe to generate the executable from the Python code.
```
#
# TODO: prior steps to install dependencies on Windows
#

# Generate command line client executable
> python setup.py py2exe
# Test the executable
> dist\semaphor-ldap.exe --help

# Generate Windows Service executable
> python windows_service\setup.py py2exe
# Test executable
> dist\semaphor-ldap-service.exe install
> dist\semaphor-ldap-service.exe start
```
