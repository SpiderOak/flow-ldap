"""
local_db.py

semaphor-ldap local DB functionality.
"""

import logging
import sqlite3
import sqlitebck

from flow import Flow

from src import app_platform


LOG = logging.getLogger("local_db")


BACKUP_FILENAME_SUFFIX = "-backup"


class LocalDB(object):
    """Encapsulates semaphor-ldap local DB operations."""

    def __init__(self, schema_file_name, db_file_name=""):
        self.db_file_name = db_file_name or app_platform.local_db_path()
        LOG.info("using '%s' database", self.db_file_name)
        db_conn = self._get_connection()
        with open(schema_file_name, "r") as schema_file:
            db_conn.executescript(schema_file.read())
        db_conn.commit()
        db_conn.close()

    def _get_connection(self):
        """Returns a connection to the local DB."""
        db_conn = sqlite3.connect(self.db_file_name)
        db_conn.row_factory = sqlite3.Row
        return db_conn

    def check_connection(self):
        """Tries a connection to the DB.
        It throws a sqlite3.Error exception if it failed to connect.
        """
        db_conn = self._get_connection()
        db_conn.close()

    def entries_to_setup(self, db_conn):
        """Get accounts that are on LDAP but not on local DB and
        are marked as enabled on LDAP. These accounts should be setup.
        By setup we mean Semaphor-LDAP will create Semaphor accounts
        for them.
        """
        cur = db_conn.cursor()
        cur.execute(
            """select lg.uniqueid, lg.email, lg.enabled
            from ldap_group lg
            left join ldap_account la on lg.uniqueid = la.uniqueid
            where lg.enabled and la.uniqueid is null and
            not exists(select 1 from ldap_account where email = lg.email)
            """,
        )
        accounts = cur.fetchall()
        cur.close()
        return accounts

    def entries_to_retry_setup(self, db_conn):
        """Get accounts that are on LDAP and on our DB,
        but they are currently marked as 'ldap lock'ed.
        These accounts may have changed username,
        and the bot is now ready to take control of the
        account.
        """
        cur = db_conn.cursor()
        cur.execute(
            """select lg.uniqueid, lg.email, lg.enabled
            from ldap_group lg
            left join ldap_account la on lg.uniqueid = la.uniqueid
            left join semaphor_account sa on la.id = sa.ldap_account
            where lg.enabled and sa.lock_state = %d
            """ % Flow.LDAP_LOCK,
        )
        accounts = cur.fetchall()
        cur.close()
        return accounts

    def entries_to_update_lock(self, db_conn):
        """Get accounts that we track on our local DB and should
        be 'full lock'ed or unlocked from 'full lock'.
        """
        cur = db_conn.cursor()
        cur.execute(
            """/* ldaped accounts with 'enabled' mismatch. */
            select lg.uniqueid as uniqueid, lg.email as email,
            lg.enabled as enabled, sa.lock_state as lock_state
            from ldap_group lg
            left join ldap_account la on lg.uniqueid = la.uniqueid
            left join semaphor_account sa on la.id = sa.ldap_account
            where ((not lg.enabled and la.enabled) or
                   (lg.enabled and not la.enabled))

            union

            /* ldaped accounts not present in ldap but present in our db
             * and currently enabled
             */
            select la.uniqueid as uniqueid, la.email as email, 0 as enabled,
            sa.lock_state as lock_state
            from ldap_account la
            left join ldap_group lg on la.uniqueid = lg.uniqueid
            left join semaphor_account sa on la.id = sa.ldap_account
            where la.enabled != 0 and lg.uniqueid is null
            """,
        )
        accounts = cur.fetchall()
        cur.close()
        return accounts

    def update_uids(self, db_conn):
        """Update 'uniqueid's of accounts that don't match our local DB.
        E.g., if we have:
         - LDAP: email=john@example.com, uniqueid=X,
         - DB: email=john@example.com, uniqueid=Y,
        Then this method will update our local DB entry for
        'john@example.com' with 'uniqueid=X'.
        We currently consider the 'email' as the identifier of EndUsers.
        """
        cur = db_conn.cursor()
        cur.execute(
            """select lg.uniqueid, lg.email
            from ldap_group lg
            left join ldap_account la on lg.email = la.email
            where lg.uniqueid != la.uniqueid
            """,
        )
        accounts = cur.fetchall()
        accounts_values = [
            (account["uniqueid"], account["email"])
            for account in accounts
        ]
        cur.executemany(
            """update ldap_account
            set uniqueid = ?
            where email = ?
            """,
            accounts_values,
        )
        # Commit to update uniqueids on local DB
        db_conn.commit()
        cur.close()

    def delta(self, ldap_accounts):
        """It will first update (commit) uniqueids
        on our local db to match LDAP.
        Then return (not execute) the actions
        to run for our local DB to match LDAP.
        """
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        cur.execute(
            """/* Create a temp table w/ same cols as ldap_account */
            create temporary table ldap_group
            as select * from ldap_account where 0
            """,
        )
        ldap_account_values = [
            (ldap_account["uniqueid"], ldap_account["email"],
             ldap_account["enabled"])
            for ldap_account in ldap_accounts
        ]
        cur.executemany(
            """insert into ldap_group
            (uniqueid, email, enabled)
            values (?, ?, ?)
            """,
            ldap_account_values,
        )
        cur.close()

        # Update uniqueids on local DB first
        self.update_uids(db_conn)

        # Determine actions, but we do not execute them
        delta_changes = {}
        delta_changes["setup"] = self.entries_to_setup(db_conn)
        delta_changes["retry_setup"] = self.entries_to_retry_setup(db_conn)
        delta_changes["update_lock"] = self.entries_to_update_lock(db_conn)

        db_conn.close()

        # Return actions to the caller
        return delta_changes

    def create_account(self, ldap_data, semaphor_data):
        """Create account entries with:
        - ldap_data for ldap_account table.
        - semaphor_data for semaphor_account table.
        """
        assert(ldap_data)
        assert(semaphor_data)
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        # Create entry on the ldap_account table first
        ldap_data_values = (
            ldap_data["uniqueid"], ldap_data["email"],
            ldap_data["enabled"],
        )
        cur.execute(
            """insert into ldap_account
            (uniqueid, email, enabled)
            values (?, ?, ?)
            """,
            ldap_data_values,
        )
        # Create entry on the semaphor_account table
        semaphor_data_values = (
            cur.lastrowid,
            semaphor_data.get("id"),
            semaphor_data.get("password"),
            semaphor_data.get("L2"),
            semaphor_data.get("lock_state"),
        )
        cur.execute(
            """insert into semaphor_account
            (ldap_account, semaphor_guid, password, L2, lock_state)
            values
            (?, ?, ?, ?, ?)
            """,
            semaphor_data_values,
        )
        db_conn.commit()
        cur.close()
        db_conn.close()
        return True

    def get_account(self, username):
        """Get all available local DB data of the given username.
        Returns a dict with the following keys:
        'uniqueid', email', 'enabled',
        'semaphor_guid', 'password', 'L2' and 'lock_state'.
        """
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        cur.execute(
            "select * from ldap_account where email = ?",
            (username,),
        )
        ldap_account = cur.fetchone()
        cur.execute(
            """select semaphor_guid, password, L2, lock_state
            from semaphor_account
            where ldap_account = ?
            """,
            (ldap_account["id"],),
        )
        semaphor_account = cur.fetchone()
        account = {}
        account.update(ldap_account)
        account.update(semaphor_account)
        cur.close()
        db_conn.close()
        return account

    def update_semaphor_account(self, username, semaphor_data):
        """Update 'semaphor_account' DB entry for the given username
        with the provided 'semaphor_data'.
        """
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        cur.execute(
            "select id from ldap_account where email = ?",
            (username,),
        )
        ldap_account_id = cur.fetchone()
        if not ldap_account_id:
            LOG.error(
                "username '%s' not found on DB",
                username,
            )
            return False
        cur.execute(
            """update semaphor_account
            set semaphor_guid = ?, password = ?, L2 = ?, lock_state = ?
            where ldap_account = ?
            """, (
                semaphor_data["id"],
                semaphor_data["password"],
                semaphor_data["L2"],
                semaphor_data["lock_state"],
                ldap_account_id[0],
            ),
        )
        db_conn.commit()
        cur.close()
        db_conn.close()
        return True

    def update_lock(self, ldap_account):
        """Updates the 'enabled' state on the 'ldap_account' table
        for the given account, and also updates the 'lock_state'
        column of the 'semaphor_account' table.
        It only updates the semaphor_account.lock_state if it is
        not ldap-locked.
        """
        uniqueid = ldap_account["uniqueid"]
        enabled = ldap_account["enabled"]
        semaphor_lock_state = \
            Flow.UNLOCK if enabled else Flow.FULL_LOCK
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        # Get ldap_account entry id
        cur.execute(
            "select id from ldap_account where uniqueid = ?",
            (uniqueid,),
        )
        row = cur.fetchone()
        if not row:
            LOG.error(
                "update_lock(%s): account does not exist.",
                uniqueid,
            )
            return False
        ldap_account_entry_id = row[0]
        cur.execute(
            """update ldap_account
            set enabled = ?
            where id = ?
            """, (
                enabled,
                ldap_account_entry_id,
            ),
        )
        # Update ldap_account entry if not ldap-locked
        if ldap_account["lock_state"] != Flow.LDAP_LOCK:
            cur.execute(
                """update semaphor_account
                set lock_state = ?
                where ldap_account = ?
                """, (
                    semaphor_lock_state,
                    ldap_account_entry_id,
                ),
            )
        db_conn.commit()
        cur.close()
        db_conn.close()
        return True

    def get_db_accounts(self):
        """Returns all the accounts on the local db."""
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        cur.execute(
            """select email, uniqueid, enabled, semaphor_guid, lock_state
            from ldap_account la
            left join semaphor_account sa on la.id = sa.ldap_account
            """,
        )
        accounts = []
        for row_account in cur.fetchall():
            account_map = {}
            account_map.update(row_account)
            accounts.append(account_map)
        cur.close()
        db_conn.close()
        return accounts

    def get_enabled_ldaped_accounts(self):
        """Returns the semaphor account ids of the ldaped accounts,
        that is, the accounts under the control of the bot.
        Returns a set of semaphor account ids.
        """
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        cur.execute(
            """select semaphor_guid as id
            from semaphor_account sa
            left join ldap_account la on la.id = sa.ldap_account
            where lock_state = %d and enabled
            """ % Flow.UNLOCK,
        )
        account_ids = [account[0] for account in cur.fetchall()]
        cur.close()
        db_conn.close()
        return account_ids

    def run_backup(self):
        """Creates a backup database file and returns its file name."""
        db_conn = self._get_connection()
        backup_filename = \
            "%s%s" % (self.db_file_name, BACKUP_FILENAME_SUFFIX)
        db_back_conn = sqlite3.connect(backup_filename)
        sqlitebck.copy(db_conn, db_back_conn)
        db_conn.close()
        db_back_conn.close()
        return backup_filename

    def check_db(self):
        """Health check for DB. Returns a string with the result."""
        try:
            self.check_connection()
        except Exception as exception:
            db_state = "ERROR: %s" % str(exception)
        else:
            db_state = "OK"
        return db_state
