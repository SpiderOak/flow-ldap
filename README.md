# semaphor-ldap

`semaphor-ldap` is a daemon+client app to enable the use of SpiderOak Semaphor with customer LDAP credentials.

## Functionality

- Keeps LDAP accounts in sync with Semaphor accounts.
- Two modes of operation, `daemon/server` and `client`:
  - The `server` mode starts a daemon in the background, it performs the following operations:
    - LDAP account polling (via LDAP Group/OU listing).
    - Semaphor domain account management.
    - Provides an HTTP JSON-RPC API.
  - The `client` mode communicates with the daemon server via the HTTP JSON-RPC API.

## Install

Setup your virtualenv:
```bash
$ mkdir venv
$ virtualenv venv
$ . venv/bin/activate
```
Install dependencies (this will be improved once we go to PyPi)
```bash
# Install flow-python
$ git clone git@github.com:SpiderOak/flow-python.git
$ cd flow-python
$ python setup.py install

# Install ldap-reader
$ git clone git@github.com:SpiderOak/ldap-reader.git
$ cd ldap-reader
$ python setup.py install

# Install remaining requirements 
$ pip install -r requirements.txt
```
Install `semaphor-ldap`:
```bash
$ python setup.py install
```

## Usage

`semaphor-ldap` has two modes of operation: `server` and `client`.

First (for now) you must set an env variable `$SEMLDAP_CONFIGDIR` for the config directory:
```bash
$ export SEMLDAP_CONFIGDIR=/home/user/.config/semaphor-ldap
```
Run on server mode (this creates and populates the config dir)
```bash
$ semaphor-ldap --debug server --config config/sample.cfg
```
Run the client (reads necessary config from the config dir)
```bash
# can-auth returns the result of a user auth test against LDAP
$ semaphor-ldap --debug client can-auth --username user --password password
```

## Assumptions

- LDAP and Semaphor configuration provided via config.
- Loops the provided Semaphor account:
    - If the account does not exist, it creates the account + a device (`create_local_account`).
    - If the account exists, but there's no device, it creates a device (`create_local_device`).
    - If the account and device already exist, it will use them (`start_up`). 
 
