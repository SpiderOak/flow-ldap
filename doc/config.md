# Semaphor-LDAP Service Configuration

To configure the Semaphor-LDAP service you can use the client command `config-set`. Here's the documentation for all configuration variables.

## Server Configuration

### listen-port
Local port to configure/operate the service. Default = `8080`.

### db-backup-minutes
The Semaphor-LDAP service performs a local backup every `db-backup-minutes` minutes. Default = `60`.

### ldap-sync-minutes
Frequency of the `ldap-sync` run. Default = `60`.

### excluded-accounts
Comma separated list of excluded accounts from LDAP. These accounts won't be managed by the Semaphor-LDAP service. Default = (empty).

### ldap-sync-on
Enable/Disable ldap-sync scheduled run. Possible values are `yes`/`no`. Default = `no`.

### verbose
Enable/Disable verbose. Possible values are `yes`/`no`. Default = `no`.

### log-dest
Set service logging destination. Possible values are `event` and `file` on Windows, `syslog` and `file` on Linux. Default values are `event` on Windows and `syslog` on Linux.

### disable-auto-updates
Disable auto-updates capability. Auto-updates is enabled by default, it is not recommended to disable it.

## LDAP Configuration variables

The Semaphor-LDAP service connects and retrieves accounts from an LDAP server. You need to properly configure the LDAP configuration variables to connect to your LDAP server.

### uri
LDAP Server URI. e.g. `ldap://example.com:389/`

### ldap-user
The Semaphor-LDAP service needs an LDAP username, e.g. `user@example.com`. The used `ldap-user` needs enough permissions to list members of the given LDAP group given in `group-dn`.

### ldap-pw
The Semaphor-LDAP service also needs the `ldap-user` password.

### group-dn
LDAP Group with all the accounts for which a Semaphor account will be created, e.g. `cn=MyGroup,cn=Users,dc=domain,dc=com`. Support for multiple groups is coming on later versions. If you want the Semaphor-LDAP service to handle multiple LDAP groups, then you should create one group that contains all these groups (the Semaphor-LDAP service supports nested groups).

### Vendor LDAP server variables

The need for updating the default values here may depend on your LDAP server configuration.
The default values come configured for connecting to an Active Directory LDAP server.

#### server-type
LDAP Server vendor. Possible values are: `AD`, `OpenLDAP` and `RHDS`. Default `AD`.

#### base-dn
Base distinguish name of your LDAP accounts, e.g. `dc=example,dc=com` if your accounts are of the form `john@example.com`. Default (empty).

#### dir-member-source
LDAP Attribute used to detect group members. Default `member` for `AD`.

#### dir-username-source
LDAP Attribute used to get the email/username of LDAP accounts. Default = `userPrincipalName` for `AD`.

#### dir-guid-source
Attribute used to get the uid of LDAP accounts. Default `objectGUID` = for `AD`.

#### dir-auth-source
LDAP Attribute is configured to be `dn` when the LDAP server in question, `RHDS` or `OpenLDAP` expects a full LDAP DN for the username to authenticate with. Possible values are `dn` or empty. Default = (empty) for `AD`.

#### dir-auth-username
The Semaphor-LDAP service expects an email address to authenticate against. If this isn't the actual username to authenticate against LDAP with, then we expect the Customer to have this field defined. The attribute specified in `dir-auth-username` is looked up for the LDAP object with the `dir-username-source` field presented to us as a username, and use the `dir-auth-username` contents as the username to authenticate with internally. Default = (empty).
