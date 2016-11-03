# Changelog

## 1.0.2

### Features

- Add `test-auth` command to test a user authentication. This command is useful on the initial setup of LDAP configuration variables.
- Prompt for password twice on `test-auth` and when setting `ldap-pw` config variable.

### Bugfixes

- During an ldap-sync, if a user fails, then we log the error and continue processing.
- Remove `get_auth_username` ldap check from the `check-status`. This doesn't work when the target LDAP AD has the username on other field other than `userPrincipalName`.
