# Troubleshooting

- If you see the following output when running the command line client:
  ```
  C:\Program Files\Semaphor-LDAP x64>semaphor-ldap.exe check-status
  ERROR loading the auto-connect config file, error: '[Errno 13] Permission denied: 'C:\\Windows\\system32\\config\\systemprofile\\AppData\\Local\\semaphor-ldap\\server-auto-connect.cfg''.
  On Windows, this executable must be run in cmd in Administrator mode.
  ```
  Then, as the error message says, you must start the Windows Command Prompt in Administrator mode.

- Use the `check-status` command as a health check for the Semaphor-LDAP service. If any of `flow`, `ldap`, `db` or `sync` fields do not show an `OK`, then you should check service logs.And possibly set `verbose` to `yes` to help in troubleshooting. After you are done troubleshooting, then you should set `verbose` to `no`, so that it doesn't fill `event`/`file` logging with unnecessary information. 

- If you are having a consistent issue with the service, then you should use `log-dest` to log to a file. Which can then be sent to SpiderOak CS to help troubleshooting the problem.

- By default, the Semaphor-LDAP server process listens on port `8080`. If that port is not available, then the server will terminate at startup. You can detect this scenario by looking at `file`/`event`/`syslog` logs. Here are the steps to change the port:
  - Start the server, it will terminate by its own because the port `8080` is taken, but it will generate a config file `server-config.cfg` on the config directory `C:\Windows\System32\config\systemprofile\AppData\Local\semaphor-ldap\`.
  - Change `listen-port` on `server-config.cfg` from `8080` to the desired port.
  - Start the server again.

- Accounts that belong to the domain and that are not members of the `LDAP Team` will be locked after performing the Domain Claiming step. Once the Semaphor-LDAP service is fully configured, then accounts will be given the choice to join LDAP and will therefore be unlocked.

- If the Semaphor-LDAP service does not seem to respond, then you can restart the service just like any Windows service:
  ```
  > semaphor-ldap-service.exe restart
  ```
