# core/database.py

import sqlite3
from datetime import datetime
import uuid
import logging
import json
import threading

class DatabaseHandler:
    def __init__(self, local_db_file="local_members.db"):
        self.local_db_file = local_db_file
        self.local = threading.local()

        # Configure logging
        logging.basicConfig(level=logging.INFO, filename='database.log',
                            format='%(asctime)s - %(levelname)s - %(message)s')

    def get_connection_and_cursor(self):
        """Retrieve or create a thread-local SQLite connection and cursor."""
        if not hasattr(self.local, 'connection'):
            self.local.connection = sqlite3.connect(self.local_db_file, check_same_thread=False)
            self.local.connection.execute("PRAGMA foreign_keys = ON;")  # Enable foreign keys
            self.local.cursor = self.local.connection.cursor()
            self.setup_local_db()
        return self.local.connection, self.local.cursor

    def setup_local_db(self):
        """Create members and exercise_data tables if they don't exist."""
        conn, cursor = self.get_connection_and_cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT DEFAULT 'NA',
                membership TEXT DEFAULT 'NA',
                joined_on TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exercise_data (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                exercise TEXT NOT NULL,
                set_count INTEGER,
                sets_reps TEXT,
                rep_data TEXT,
                timestamp TEXT,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES members (user_id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        logging.info("Local SQLite database setup completed.")

    # Local SQLite Methods for Members
    def get_member_info_local(self, username):
        """Retrieve member info from local SQLite DB."""
        try:
            conn, cursor = self.get_connection_and_cursor()
            cursor.execute('SELECT * FROM members WHERE username = ?', (username,))
            row = cursor.fetchone()
            if row:
                return {
                    "user_id": row[0],
                    "username": row[1],
                    "email": row[2],
                    "membership": row[3],
                    "joined_on": row[4]
                }
            return None
        except sqlite3.Error as e:
            logging.error(f"SQLite error in get_member_info_local: {e}")
            return None

    def insert_member_local(self, member_info):
        """Insert a new member into local SQLite DB."""
        try:
            conn, cursor = self.get_connection_and_cursor()
            cursor.execute('''
                INSERT INTO members (user_id, username, email, membership, joined_on)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                member_info["user_id"],
                member_info["username"],
                member_info.get("email", "NA"),
                member_info.get("membership", "NA"),
                member_info["joined_on"]
            ))
            conn.commit()
            logging.info(f"Inserted member {member_info['username']} into local DB.")
            return True
        except sqlite3.IntegrityError as e:
            logging.error(f"IntegrityError while inserting member: {e}")
            return False
        except sqlite3.Error as e:
            logging.error(f"SQLite error while inserting member: {e}")
            return False

    def delete_member_local(self, username):
        """Delete a member from local SQLite DB."""
        try:
            conn, cursor = self.get_connection_and_cursor()
            cursor.execute('DELETE FROM members WHERE username = ?', (username,))
            conn.commit()
            if cursor.rowcount > 0:
                logging.info(f"Deleted member {username} from local DB.")
                return True
            else:
                logging.warning(f"No member found with username: {username}")
                return False
        except sqlite3.Error as e:
            logging.error(f"SQLite error while deleting member: {e}")
            return False

    def get_all_members_local(self):
        """Retrieve all members from local SQLite DB."""
        try:
            conn, cursor = self.get_connection_and_cursor()
            cursor.execute('SELECT * FROM members')
            rows = cursor.fetchall()
            members = []
            for row in rows:
                members.append({
                    "user_id": row[0],
                    "username": row[1],
                    "email": row[2],
                    "membership": row[3],
                    "joined_on": row[4]
                })
            return members
        except sqlite3.Error as e:
            logging.error(f"SQLite error in get_all_members_local: {e}")
            return []

    def get_member_info(self, username):
        """Retrieve a member's information by username."""
        return self.get_member_info_local(username)
    
    def get_all_members(self):
        """Retrieve all members from local SQLite DB."""
        return self.get_all_members_local()

    # Local SQLite Methods for Exercise Data
    def insert_exercise_data_local(self, exercise_data):
        """Insert new exercise data into local SQLite DB."""
        try:
            conn, cursor = self.get_connection_and_cursor()
            cursor.execute('''
                INSERT INTO exercise_data (id, user_id, exercise, set_count, sets_reps, rep_data, timestamp, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                exercise_data["id"],
                exercise_data["user_id"],
                exercise_data["exercise"],
                exercise_data["set_count"],
                json.dumps(exercise_data["sets_reps"]),
                json.dumps(exercise_data["rep_data"]),
                exercise_data["timestamp"],
                exercise_data["date"]
            ))
            conn.commit()
            logging.info(f"Inserted exercise data for user {exercise_data['user_id']} into local DB.")
            return True
        except sqlite3.IntegrityError as e:
            logging.error(f"IntegrityError while inserting exercise data: {e}")
            return False
        except sqlite3.Error as e:
            logging.error(f"SQLite error while inserting exercise data: {e}")
            return False

    def get_exercise_data_for_user_local(self, user_id):
        """Retrieve exercise data for a specific user from local SQLite DB."""
        try:
            conn, cursor = self.get_connection_and_cursor()
            cursor.execute('SELECT * FROM exercise_data WHERE user_id = ?', (user_id,))
            rows = cursor.fetchall()
            data = []
            for row in rows:
                data.append({
                    "id": row[0],
                    "user_id": row[1],
                    "exercise": row[2],
                    "set_count": row[3],
                    "sets_reps": json.loads(row[4]) if row[4] else [],
                    "rep_data": json.loads(row[5]) if row[5] else [],
                    "timestamp": row[6],
                    "date": row[7]
                })
            return data
        except sqlite3.Error as e:
            logging.error(f"SQLite error in get_exercise_data_for_user_local: {e}")
            return []

    def get_exercise_data_for_user(self, user_id):
        """Retrieve exercise data for a specific user from local SQLite DB."""
        return self.get_exercise_data_for_user_local(user_id)

    def close_connections(self):
        """Close all thread-local connections."""
        if hasattr(self.local, 'connection'):
            self.local.connection.close()
            logging.info("Closed thread-local SQLite connection.")
