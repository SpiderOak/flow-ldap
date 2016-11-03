[![Build Status](https://travis-ci.org/SpiderOak/flow-ldap.svg?branch=master)](https://travis-ci.org/SpiderOak/flow-ldap)

# semaphor-ldap

`semaphor-ldap` is a server+client app to enable the use of SpiderOak Semaphor with customer LDAP credentials.

## Functionality and Features

- It offers a `server` application and a command line `client` application.
  - The server runs in the background as a daemon/service.
  - The command line client is used to configure the server.
- The server runs an scheduled `ldap-sync` operation, which performs the following actions:
  - Read LDAP accounts from a specified `LDAP Group` and creates Semaphor account for each entry.
  - Locks/Unlocks accounts depending on the account LDAP state.
  - Locks existing accounts prior to the server installation and locks them in a way they have to either join LDAP or change username (aka `ldap-locked`)
- Runs a scheduled backup of local data (it uses a private channel as a backup mechanism).
- It creates a LOG channel and adds admins of the LDAP team to it, ERROR messages are then logged to this channel.
- It automatically adds accounts to the Semaphor LDAP Team and prescribed channels.
- It allows signing in to Semaphor using LDAP credentials.
- Reports logging to `Event` on Windows and `syslog` in Linux (it can also log to a file).

## Documentation

- [Installation Guide](doc/install.md)
- [Usage Guide](doc/usage.md)
- [Changelog](CHANGELOG.md)
