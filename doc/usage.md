# Semaphor-LDAP Usage Guide

Semaphor-LDAP consists of a server application and a command line client.
The server is intended to run as a daemon in Unix and as a service in Windows.
The command line client provides commands to configure the server and retrieve information about
the users tracked by the Semaphor-LDAP server.
  
## Terminology

### Directory Management Account (aka DMA)
Semaphor account that manages the Semaphor integration with LDAP. The Semaphor-LDAP server runs this account.
### LDAP Team
The `LDAP Team` is the Semaphor Team configured in the LDAP setup. It is the team managed by the Directory Management Account running in the Semaphor-LDAP server. All accounts under the domain are automatically added to this team.
### Admin Accounts
Semaphor `LDAP Team` admins are considered admins of the domain by the Semaphor-LDAP. These accounts are automatically added to the LOG channel.
### Prescribed Channels 
These are channels within the LDAP Team to which accounts are automatically added to. To turn a channel into a prescribed channel, an admin must make the DMA an admin of such channel. Admin accounts are the only accounts allowed to add the DMA to a channel.
### Log Channel
Semaphor-LDAP will send ERROR messages to the log channel. Only admins will be added to such channel.
### Excluded Accounts
These accounts are excluded from the LDAP sync algorithm and therefore not handled by Semaphor-LDAP.
Excluded accounts are specified as a comma-separated list in the `excluded-accounts` configuration variable.
### Semaphor Account States
A user Semaphor account under LDAP control can be in one of three states:
- `unlocked`: Under control of the DMA and fully operational.
- `ldap-locked`: Account is locked with only two possible actions: join LDAP or change username. 
- `full-locked`: Account has been locked by the DMA because it is disabled on LDAP. The account cannot operate on the flow service whatsoever.

## Server Application

The performs the following main operations:
 - LDAP account polling (via LDAP Group/OU listing).
 - Semaphor domain account management.
 - Provide an HTTP JSON-RPC API.

The following command starts the Semaphor-LDAP server.
It will generate its own default config and an auto-connect config for the command line client
```
$ semaphor-ldap server
```

## Command Line Client Application

The `client` mode communicates with the Semaphor-LDAP server via the HTTP JSON-RPC API.
Currently, both the client and the server must run in the same host.

Use the `--help` option to get a list of the available client commands:
```
$ semaphor-ldap client --help
```

-------

Once the server is running we can check its current state via the `check-status` command.
On the first run you will probably see the following output:
```
$ semaphor-ldap client check-status
Checking Semaphor-LDAP server status...
Server status:
- db = OK
- flow = ERROR: DMA is not configured yet
- ldap = ERROR: {'desc': "Can't contact LDAP server"}
- sync = OFF
```
The first `flow = ERROR` means you haven't configured your Directory Management Account.
The second `ldap = ERROR` means the current configuration for connecting to your LDAP server is invalid. 

-------

Let's configure the LDAP values first, 
you can see the current configuration with the 'config-list' command:
```
$ semaphor-ldap client config-list
Getting config list...
== LDAP Config ==
  - admin-user = cn=admin,dc=domain,dc=com      # (1)
  - dir-username-source = userPrincipalName
  - group-dn = ou=People,dc=domain,dc=com       # (2)
  - server-type = AD
  - uri = ldap://domain.com                     # (3)
  - dir-auth-source = dn
  - admin-pw = ********                         # (4)
  - base-dn = dc=domain,dc=com                  # (5)
  - dir-guid-source = objectGUID
  - dir-member-source = member
== Server Config ==
  - db-backup-minutes = 60
  - listen-port = 8080
  - verbose = no
  - ldap-sync-on = no
  - ldap-sync-minutes = 60
  - log-dest = file
  - excluded-accounts =
```

To configure LDAP you need to update the five config values marked above, to do that we have to use the `config-set` command

```
$ semaphor-ldap client config-set --key uri --value ldap://example.com:389
Setting config 'uri'...

$ semaphor-ldap client config-set --key admin-user --value Administrator@example.com
Setting config 'admin-user'...

$ semaphor-ldap client config-set --key admin-pw
Password:
Setting config 'admin-pw'...

$ semaphor-ldap client config-set --key base-dn --value dc=example,dc=com
Setting config 'base-dn'...

$ semaphor-ldap client config-set --key group-dn --value cn=MyGroup,cn=Users,dc=example,dc=com
Setting config 'group-dn'...
```

Now we should see an "OK" on the ldap status:

```
$ semaphor-ldap client check-status
Checking Semaphor-LDAP server status...
Server status:
- db = OK
- flow = ERROR: DMA is not configured yet
- ldap = OK
- sync = OFF
```

-------

Before continuing with flow, we should list the users that will be controlled by Semaphor-LDAP server by using the `group-userlist` command.
This option will list the users that belong to the group specified in the `group-dn` config variable.

```
$ semaphor-ldap client group-userlist
Getting list of accounts from the configured LDAP group...
john@example.com, uid = fc6dd73a-ebe5-4ac2-8a54-b6fe89638e8f, ldap-state = enabled
alice@example.com, uid = dea2c6b5-6123-4e18-be5b-92b33506c3a5, ldap-state = enabled
mark@example.com, uid = deb32ba5-6223-3a1b-3e5b-93324506c3a5, ldap-state = disabled
[...]
```
If everything looks good, we can continue with the flow setup.

-------

We can now create the Diretory Management Account (aka DMA) to manage the domain:
To create a DMA we need the Directory Management Key (aka DMK)
You need to securely store the generated username and recovery-key.
```
$ semaphor-ldap client create-account --dmk NNBTWOQMSTHOF27VTODWKZF63CLUVSS4A22QNK4WEHYQNS7BLTHQ
Creating Directory Management Account...
The DMA account was created, please securely store the following credentials:
- Username = DMAPXZJN7QKPR
- Recovery Key = USKONS7UYKDFATRPFMGSUACPHAVKUFC3
A Team Join Request was sent to the LDAP Team = 7QXVLPNHOFJZJTIOL2GHV4YFDZDRQV54
BNNCYQ7OPLYBTGZO4ZCQ.
To finish the setup please accept the request and make the DMA an admin.
```

-------

Now you need to go to Semaphor and accept the DMA Team Join Request to the LDAP Team and also make it an admin of the Team.
After all this, we should see an "OK" on the flow status
```
$ semaphor-ldap client check-status
Checking Semaphor-LDAP server status...
Server status:
- db = OK
- flow = OK
- ldap = OK
- sync = OFF
```

-------

With LDAP and the Flow service properly configured we can enable the `LDAP sync`.
The `LDAP sync` will run every `ldap-sync-minutes` minutes.
It creates Semaphor accounts for the accounts listed in the given LDAP group.
The LDAP sync will also lock/unlock Semaphor accounts by looking at the LDAP state.
```
$ semaphor-ldap client ldap-sync-enable
$ semaphor-ldap client check-status
Checking Semaphor-LDAP server status...
Server status:
- db = OK
- flow = OK
- ldap = OK
- sync = ON
```
With `sync = ON` we can now proceed to trigger a manual `ldap-sync`

-------

We could wait for the first scheduled `LDAP sync` run, but we can also trigger one manually:
```
$ semaphor-ldap client ldap-sync-trigger
Trigerring an LDAP sync...
```

Accounts should be ready after the LDAP sync, we can check their state by using the `db-userlist` command. 
  - `unlocked` are Semaphor accounts owned by Semaphor-LDAP.
  - `ldap-locked` are Semaphor accounts that are locked and given the choice between join to LDAP or change username
  - `full-locked` are Semaphor accounts that cannot operate, they correspond to a `disabled` LDAP state.
```
$ semaphor-ldap client db-userlist
Retrieving users from the local database...
john@example.com, uid = fc6dd73a-ebe5-4ac2-8a54-b6fe89638e8f, ldap-state = disabled, semaphor-guid = 73M5UDSR263J7F3RQJO4NIISN3WL4LXJU3YC6JNHM7VLFYFNJ63A, semaphor-lock-state = unlocked
alice@example.com, uid = dea2c6b5-6123-4e18-be5b-92b33506c3a5, ldap-state = enabled, semaphor-guid = 46YIUGBAWFNOWRA53E6UXTJH5EQ5FIP3ONDGEQZCTTBH7UK6QMEA, semaphor-lock-state = ldap-locked
...
```

-------

With accounts created and the Semaphor-LDAP server up and running, we can retrieve the Semaphor Join LDAP URI and share it to employees so they can start using Enterprise Semaphor.
```
$ semaphor-ldap client dma-fingerprint
Getting Directory Management Account fingerprint...
Fingerprint = LAA75OEDLBUV4H6IKNFJW5GBOGEBLPXA5MKLLXL7XJE6WQM5SXJA
URI = semaphor://enterprise-sign-in/LAA75OEDLBUV4H6IKNFJW5GBOGEBLPXA5MKLLXL7XJE6WQM5SXJA
```

-------

You can redirect server logging to one of `event` (on Windows), `syslog` (on Linux) and `file` by using the `log-dest` command:
```
$ semaphor-ldap client log-dest --target event
Setting log destination to file...
```

-------

In case your server crashes and you are not able to recover the Semaphor-LDAP config directory, you can install Semaphor-LDAP on another device using the `username` and `recovery-key`. This command will restore your local DB (and in future relases your configuration).
```
$ semaphor-ldap client create-device --username DMAPXZJN7QKPR --recovery-key USKONS7UYKDFATRPFMGSUACPHAVKUFC3
```

## Windows

In Windows, we have two executables:

- `semaphor-ldap-service.exe`: This is the server executable that runs the Semaphor-LDAP server as a Windows Service.
  You can use the executable just like any Windows Service application:
  ```
  > semaphor-ldap-service.exe {install,start,stop}
  ```

- `semaphor-ldap.exe`: This is the command line client executable.
  E.g. to execute a `check-status`:
  ```
  > semaphor-ldap.exe check-status
  ```

## Local Configuration Directory

Server configuration and local DBs are located under:

  - Windows: `C:\Windows\System32\config\systemprofile\AppData\Local\semaphor-ldap\`
  - Linux: `~/.config/semaphor-ldap/`
  - Linux: `~/Library/Application Support/semaphor-ldap/`

