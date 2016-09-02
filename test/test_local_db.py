#! /usr/bin/env python
import sys
import os
import unittest
import random
import string

import sqlite3

# flow-ldap root dir
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from src.db import local_db

SCHEMA_FILE = os.path.join(
    ROOT_DIR, 
    "schema/dma.sql",
)
TEST_DIR = os.path.join(
    ROOT_DIR, 
    "test",
)

class TestLocalDB(unittest.TestCase):

    PASSWORD = "PW"*16
    L2 = "L2"*22

    def setUp(self):
        self.db_file = os.path.join(
            TEST_DIR, 
            "DMA%s.sqlite" % self.id(),
        )
        self.db = local_db.LocalDB(
            SCHEMA_FILE,
            self.db_file,
        )

    def gen_sem_guid(self):
        return "".join(random.choice(string.ascii_lowercase) for _ in range(52))

    def create_account_db_entries(self, entries):
        db_conn = sqlite3.connect(self.db_file)
        db_conn.row_factory = sqlite3.Row
        cur = db_conn.cursor()
        for entry in entries:
            ldap_data = {
                "uniqueid": entry[0],
                "email": entry[1],
                "enabled": entry[2],
            }
            if entry[3] != 2:
                sem_data = {
                    "semaphor_guid": self.gen_sem_guid(),
                    "password": self.PASSWORD,
                    "level2_secret": self.L2,
                    "state": entry[3],
                }
            else:
                sem_data = {
                    "state": 2,
                }
            self.db.create_account(ldap_data, sem_data)
        db_conn.commit()
        db_conn.close()

    def test_entries_to_setup(self):
        # This is what comes from LDAP
        ldap_entries = [
            # Existing unchanged entry
            {"uniqueid": "1", "email": "john@example.com", "enabled": 1},
            # Alice should setup
            {"uniqueid": "2", "email": "alice@example.com", "enabled": 1},  # (1)
            # Carl is disabled from scratch, so don't setup
            {"uniqueid": "3", "email": "carl@example.com", "enabled": 0},
            # back@example.com has his uniqueid updated
            {"uniqueid": "5", "email": "back@example.com", "enabled": 1},
        ]
        # This is what we have on the DB
        self.create_account_db_entries([
            ("1","john@example.com", True, 1),
            ("4","back@example.com", True, 1),
        ])
        # Run the delta
        delta_entries = self.db.delta(ldap_entries)
        self.assertFalse(delta_entries["retry_setup"])
        self.assertFalse(delta_entries["update_lock"])
        setup = delta_entries["setup"]
        self.assertTrue(setup)
        self.assertEqual(len(setup), 1)
        self.assertEqual(setup[0]["email"], "alice@example.com")  # (1)

    def test_entries_to_retry(self):
        # This is what comes from LDAP
        ldap_entries = [
            # Existing unchanged entry, should not retry
            {"uniqueid": "1", "email": "john@example.com", "enabled": 1},
            # Alice should retry
            {"uniqueid": "2", "email": "alice@example.com", "enabled": 1},  # (1)
            # Carl is disabled, so should not retry
            {"uniqueid": "3", "email": "carl@example.com", "enabled": 0},
            # back@example.com has his uniqueid updated, and enabled, should retry
            {"uniqueid": "5", "email": "back@example.com", "enabled": 1},  # (2)
        ]
        # This is what we have on the DB
        self.create_account_db_entries([
            ("1","john@example.com", True, 1),
            ("2","alice@example.com", True, 2),
            ("3","carl@example.com", True, 2),
            ("4","back@example.com", True, 2),
        ])
        # Run the delta
        delta_entries = self.db.delta(ldap_entries)
        self.assertFalse(delta_entries["setup"])
        self.assertFalse(delta_entries["update_lock"])
        retry = delta_entries["retry_setup"]
        self.assertTrue(retry)
        self.assertEqual(len(retry), 2)
        self.assertEqual(retry[0]["email"], "alice@example.com")  # (1)
        self.assertEqual(retry[1]["email"], "back@example.com")  # (2)

    def test_entries_to_update_lock(self):
        # This is what comes from LDAP
        ldap_entries = [
            # Existing unchanged entry, should not change lock
            {"uniqueid": "1", "email": "john@example.com", "enabled": 1},
            # Alice should be locked
            {"uniqueid": "2", "email": "alice@example.com", "enabled": 0},  # (1)
            # Carl is disabled, and already disabled on the DB, nothing to do
            {"uniqueid": "3", "email": "carl@example.com", "enabled": 0},
            # Neil is disabled on the DB, so now it needs to be enabled
            {"uniqueid": "4", "email": "neil@example.com", "enabled": 1},  # (2)
            # back@example.com has his uniqueid updated, and db enabled, should be disabled
            {"uniqueid": "6", "email": "back@example.com", "enabled": 0},  # (3)
            # mark@example.com has been disabled, and db enabled, and ldap locked, nothing to do
            {"uniqueid": "7", "email": "mark@example.com", "enabled": 0},
        ]
        # This is what we have on the DB
        self.create_account_db_entries([
            ("1","john@example.com", True, 1),
            ("2","alice@example.com", True, 1),
            ("3","carl@example.com", False, 1),
            ("4","neil@example.com", False, 1),
            ("5","back@example.com", True, 1),
            ("7","mark@example.com", True, 2),
        ])
        # Run the delta
        delta_entries = self.db.delta(ldap_entries)
        self.assertFalse(delta_entries["setup"])
        self.assertFalse(delta_entries["retry_setup"])
        update_lock = delta_entries["update_lock"]
        self.assertTrue(update_lock)
        self.assertEqual(len(update_lock), 3)
        self.assertEqual(update_lock[0]["email"], "alice@example.com")  # (1)
        self.assertEqual(update_lock[0]["enabled"], 0)
        self.assertEqual(update_lock[1]["email"], "neil@example.com")  # (2)
        self.assertEqual(update_lock[1]["enabled"], 1)
        self.assertEqual(update_lock[2]["email"], "back@example.com")  # (3)
        self.assertEqual(update_lock[2]["enabled"], 0)

    def tearDown(self):
        os.remove(self.db_file)


if __name__ == '__main__':
    unittest.main()
