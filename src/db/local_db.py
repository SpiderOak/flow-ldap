"""
local_db.py

semaphor-ldap local DB functionality.
"""

import logging
import sqlite3
import sqlitebck


LOG = logging.getLogger("local_db")

# account state values of local DB account
UNLOCK = 1
LDAP_LOCK = 2
FULL_LOCK = 3

BACKUP_FILENAME_SUFFIX = "-backup"


class LocalDB(object):
    """Encapsulates semaphor-ldap local DB operations."""

    def __init__(self, schema_file_name, db_file_name):
        self.schema_file_name = schema_file_name
        self.db_file_name = db_file_name
        LOG.debug("using '%s' database", self.db_file_name)
        db_conn = self._get_connection()
        with open(schema_file_name) as schema_file:
            db_conn.executescript(schema_file.read())
        db_conn.commit()
        db_conn.close()

    def _get_connection(self):
        db_conn = sqlite3.connect(self.db_file_name)
        db_conn.row_factory = sqlite3.Row
        return db_conn

    def entries_to_setup(self, db_conn):
        """Get accounts that are on LDAP but not on local DB and
        they are marked as enabled on LDAP.
        These accounts should be setup.
        """
        cur = db_conn.cursor()
        cur.execute(
            """select lg.uniqueid, lg.email, 
            lg.firstname, lg.lastname, lg.enabled
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
            """select lg.uniqueid, lg.email, 
            lg.firstname, lg.lastname, lg.enabled
            from ldap_group lg 
            left join ldap_account la on lg.uniqueid = la.uniqueid 
            left join semaphor_account sa on la.id = sa.ldap_account
            where lg.enabled and sa.state = 2
            """,
        )
        accounts = cur.fetchall()
        cur.close()
        return accounts

    def entries_to_update_lock(self, db_conn):
        """Get accounts that the bot controls (ldaped) and should 
        be 'full lock'ed or unlocked from 'full lock'.
        """
        cur = db_conn.cursor()
        cur.execute(
            """/* ldaped accounts with 'enabled' mismatch. */
            select lg.uniqueid as uniqueid, lg.email as email,
            lg.firstname as firstname, lg.lastname as lastname, 
            lg.enabled as enabled
            from ldap_group lg
            left join ldap_account la on lg.uniqueid = la.uniqueid
            left join semaphor_account sa on la.id = sa.ldap_account
            where (sa.state = 1 or sa.state = 3) and
            ((not lg.enabled and la.enabled) or 
             (lg.enabled and not la.enabled))

            union

            /* ldaped accounts not present in ldap but present in our db
             * and currently enabled 
             */
            select la.uniqueid as uniqueid, la.email as email,
            la.firstname as firstname, la.lastname as lastname, 
            0 as enabled
            from ldap_account la
            left join ldap_group lg on la.uniqueid = lg.uniqueid
            left join semaphor_account sa on la.id = sa.ldap_account
            where la.enabled != 0 and sa.state = 1 and lg.uniqueid is null
            """,
        )
        accounts = cur.fetchall()
        cur.close()
        return accounts

    def entries_to_update_uid_enabled(self, db_conn):
        """Get accounts that the bot controls (ldaped) and should 
        be 'full lock'ed or unlocked from 'full lock'.
        """
        cur = db_conn.cursor()
        cur.execute(
            """/* accounts that reappeared on ldap and are disabled on our db */
            select lg.uniqueid as uniqueid, lg.email as email,
            lg.firstname as firstname, lg.lastname as lastname, 
            lg.enabled as ldap_enabled, la.enabled as db_enabled
            from ldap_group lg
            left join ldap_account la on lg.email = la.email
            where lg.uniqueid != la.uniqueid
            """,
        )
        accounts = cur.fetchall()
        cur.close()
        return accounts

    def entries_to_update_ldap_data(self, db_conn):
        """Get accounts that need their LDAP data updated.
        That is (for now) firstname and lastname.
        """
        cur = db_conn.cursor()
        cur.execute(
            """select lg.uniqueid as uniqueid,
            lg.firstname as firstname, lg.lastname as lastname
            from ldap_group lg
            left join ldap_account la on lg.uniqueid = la.uniqueid
            where la.firstname != lg.firstname or la.lastname != lg.lastname
            """,
        )
        accounts = cur.fetchall()
        cur.close()
        return accounts

    def update_uids(self, db_conn):
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
        cur.close()

    def delta(self, ldap_accounts):
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        # Create temporary tables with retrieved ldap info
        cur.execute(
            """/* Create a temp table w/ same cols as ldap_account */
            create temporary table ldap_group 
            as select * from ldap_account where 0
            """,
        )
        ldap_account_values = [
            (ldap_account["uniqueid"], ldap_account["email"],
             ldap_account["firstname"], ldap_account["lastname"],
             ldap_account["enabled"]) 
            for ldap_account in ldap_accounts
        ]
        cur.executemany(
            """insert into ldap_group
            (uniqueid, email, firstname, lastname, enabled) 
            values (?, ?, ?, ?, ?)
            """,
            ldap_account_values,
        )
        cur.close()

        self.update_uids(db_conn)

        delta_changes = {}
        delta_changes["setup"] = self.entries_to_setup(db_conn)
        delta_changes["retry_setup"] = self.entries_to_retry_setup(db_conn)
        delta_changes["update_lock"] = self.entries_to_update_lock(db_conn)
        delta_changes["update_ldap_data"] = \
            self.entries_to_update_ldap_data(db_conn)

        db_conn.close()
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
            ldap_data["firstname"], ldap_data["lastname"],
            ldap_data["enabled"],
        ) 
        cur.execute(
            """insert into ldap_account 
            (uniqueid, email, firstname, lastname, enabled) 
            values (?, ?, ?, ?, ?)
            """, 
            ldap_data_values,
        )
        # Create entry on the semaphor_account table
        semaphor_data_values = (
            cur.lastrowid, 
            semaphor_data.get("id"),
            semaphor_data.get("password"), 
            semaphor_data.get("level2_secret"),
            semaphor_data.get("state"),
        ) 
        cur.execute(
            """insert into semaphor_account
            (ldap_account, semaphor_guid, password, L2, state)
            values 
            (?, ?, ?, ?, ?)
            """,
            semaphor_data_values,
        )
        db_conn.commit()
        db_conn.close()
        return True
        
    def get_account(self, username):
        """Get all available local DB data of the given username."""
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        cur.execute(
            "select * from ldap_account where email = ?",
            (username,),
        )
        ldap_account = cur.fetchone()
        cur.execute(
            """select semaphor_guid, password, L2, state 
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
            set semaphor_guid = ?, password = ?, L2 = ?, state = ? 
            where ldap_account = ?
            """, (
                semaphor_data["semaphor_guid"],
                semaphor_data["password"],
                semaphor_data["L2"],
                semaphor_data["state"],
                ldap_account_id[0],
            ),
        )
        db_conn.commit()
        db_conn.close()
        return True

    def update_lock(self, ldap_account):
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        cur.execute(
            """update ldap_account
            set enabled = ? 
            where uniqueid = ?
            """, (
                ldap_account["enabled"], 
                ldap_account["uniqueid"],
            ),
        )
        db_conn.commit()
        db_conn.close()
        return True

    def update_ldap_data(self, ldap_account):
        """Updates the ldap_account entry, for now it
        only updates the firstname and lastname columns.
        """
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        cur.execute(
            """update ldap_account
            set firstname = ?, lastname = ?
            where uniqueid = ?
            """, (
                ldap_account["firstname"], 
                ldap_account["lastname"],
                ldap_account["uniqueid"]
            ),
        )
        db_conn.commit()
        db_conn.close()
        return True

    def get_ldaped_accounts(self):
        """Returns the semaphor account ids of the ldaped accounts,
        that is, the accounts under the control of the bot.
        Returns a set of semaphor account ids.
        """
        db_conn = self._get_connection()
        cur = db_conn.cursor()
        cur.execute(
            """select semaphor_guid as id
            from semaphor_account
            where state = 1
            """,
        )
        account_ids = [account[0] for account in cur.fetchall()]
        db_conn.commit()
        db_conn.close()
        return account_ids

    def run_backup(self):
        """Backups the local DB on a private Semaphor channel."""
        db_conn = self._get_connection()
        backup_filename = \
            "%s%s" % (self.db_file_name, BACKUP_FILENAME_SUFFIX)
        db_back_conn = sqlite3.connect(backup_filename)
        sqlitebck.copy(db_conn, db_back_conn)
        return backup_filename
