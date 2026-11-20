"""
Database layer. Supports MySQL (PyMySQL) and SQLite with the same API, so the
rest of the code is database-agnostic.  SQL is written with '?' placeholders
and converted to '%s' for MySQL.
"""
import sqlite3
from config import Config

SQLITE_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, phone TEXT,
        password_hash TEXT NOT NULL, role TEXT DEFAULT 'user', created_at TEXT DEFAULT (datetime('now','localtime')))""",
    """CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, specialization TEXT NOT NULL, experience_years INTEGER,
        available_days TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, fee INTEGER)""",
    """CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, doctor_id INTEGER NOT NULL,
        appt_date TEXT NOT NULL, appt_time TEXT NOT NULL, reason TEXT,
        status TEXT DEFAULT 'Booked', created_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (doctor_id) REFERENCES doctors(id))""",
    """CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT NOT NULL, detail TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')))""",
]

MYSQL_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL, email VARCHAR(120) NOT NULL UNIQUE, phone VARCHAR(20),
        password_hash VARCHAR(255) NOT NULL, role VARCHAR(10) DEFAULT 'user', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS doctors (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL, specialization VARCHAR(60) NOT NULL, experience_years INT,
        available_days VARCHAR(40) NOT NULL, start_time VARCHAR(5) NOT NULL, end_time VARCHAR(5) NOT NULL, fee INT)""",
    """CREATE TABLE IF NOT EXISTS appointments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL, doctor_id INT NOT NULL,
        appt_date VARCHAR(10) NOT NULL, appt_time VARCHAR(5) NOT NULL, reason VARCHAR(255),
        status VARCHAR(20) DEFAULT 'Booked', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (doctor_id) REFERENCES doctors(id))""",
    """CREATE TABLE IF NOT EXISTS activity_log (
        id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NULL, action VARCHAR(40) NOT NULL, detail VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
]

# (name, specialization, experience, days, start, end, fee)
SEED_DOCTORS = [
    ("Dr. Arjun Menon", "Cardiologist", 18, "Mon,Wed,Fri", "09:00", "13:00", 800),
    ("Dr. Kavya Nair", "Cardiologist", 11, "Tue,Thu,Sat", "14:00", "18:00", 700),
    ("Dr. Priya Sharma", "Dermatologist", 9, "Mon,Tue,Thu", "10:00", "16:00", 600),
    ("Dr. Rohan Verma", "Dermatologist", 14, "Wed,Fri,Sat", "09:00", "13:00", 650),
    ("Dr. Suresh Iyer", "Neurologist", 21, "Mon,Wed,Fri", "10:00", "14:00", 900),
    ("Dr. Ananya Rao", "Neurologist", 8, "Tue,Thu", "11:00", "17:00", 750),
    ("Dr. Vikram Singh", "Orthopedic", 16, "Mon,Tue,Fri", "09:00", "15:00", 700),
    ("Dr. Meera Pillai", "Orthopedic", 10, "Wed,Thu,Sat", "10:00", "14:00", 650),
    ("Dr. Karthik Subramanian", "Gastroenterologist", 15, "Mon,Thu,Fri", "09:30", "13:30", 750),
    ("Dr. Divya Krishnan", "Gastroenterologist", 7, "Tue,Wed,Sat", "14:00", "18:00", 600),
    ("Dr. Imran Khan", "Pulmonologist", 13, "Mon,Wed,Thu", "10:00", "14:00", 700),
    ("Dr. Sneha Reddy", "Pulmonologist", 9, "Tue,Fri,Sat", "09:00", "13:00", 650),
    ("Dr. Rahul Bhat", "ENT Specialist", 12, "Mon,Tue,Wed", "15:00", "19:00", 500),
    ("Dr. Lakshmi Devi", "ENT Specialist", 17, "Thu,Fri,Sat", "09:00", "13:00", 550),
    ("Dr. Aravind Kumar", "Ophthalmologist", 14, "Mon,Wed,Fri", "10:00", "16:00", 600),
    ("Dr. Nisha Joseph", "Ophthalmologist", 6, "Tue,Thu,Sat", "09:00", "13:00", 500),
    ("Dr. Sanjay Gupta", "Endocrinologist", 19, "Mon,Tue,Thu", "11:00", "15:00", 850),
    ("Dr. Farah Ali", "Endocrinologist", 10, "Wed,Fri,Sat", "10:00", "14:00", 750),
    ("Dr. Harish Chandra", "Psychiatrist", 20, "Mon,Wed,Fri", "16:00", "20:00", 900),
    ("Dr. Pooja Malhotra", "Psychiatrist", 8, "Tue,Thu,Sat", "10:00", "14:00", 800),
    ("Dr. Naveen Raj", "Urologist", 15, "Mon,Thu,Fri", "09:00", "13:00", 750),
    ("Dr. Shweta Kulkarni", "Urologist", 9, "Tue,Wed,Sat", "14:00", "18:00", 700),
    ("Dr. Deepa Natarajan", "Gynecologist", 18, "Mon,Tue,Fri", "09:00", "14:00", 800),
    ("Dr. Anitha Mohan", "Gynecologist", 12, "Wed,Thu,Sat", "10:00", "16:00", 750),
    ("Dr. Rajesh Pandey", "Pediatrician", 16, "Mon,Wed,Thu", "09:00", "13:00", 500),
    ("Dr. Swathi Menon", "Pediatrician", 7, "Tue,Fri,Sat", "10:00", "16:00", 450),
    ("Dr. Ramesh Babu", "General Physician", 22, "Mon,Tue,Wed,Thu,Fri,Sat", "09:00", "17:00", 300),
    ("Dr. Sunita Das", "General Physician", 10, "Mon,Tue,Wed,Thu,Fri", "10:00", "18:00", 350),
]


class Database:
    def __init__(self):
        self.kind = Config.DB_TYPE
        if self.kind == "mysql":
            self._ensure_mysql_database()

    # ---------- connections ----------
    def _ensure_mysql_database(self):
        import pymysql
        c = pymysql.connect(host=Config.MYSQL_HOST, port=Config.MYSQL_PORT,
                            user=Config.MYSQL_USER, password=Config.MYSQL_PASSWORD)
        with c.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DATABASE}`")
        c.commit(); c.close()

    def _connect(self):
        if self.kind == "mysql":
            import pymysql
            return pymysql.connect(host=Config.MYSQL_HOST, port=Config.MYSQL_PORT, user=Config.MYSQL_USER,
                                   password=Config.MYSQL_PASSWORD, database=Config.MYSQL_DATABASE,
                                   cursorclass=pymysql.cursors.DictCursor)
        conn = sqlite3.connect(Config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.kind == "mysql" else sql

    # ---------- public helpers ----------
    def query(self, sql, params=(), one=False):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(self._sql(sql), params)
            rows = [dict(r) for r in cur.fetchall()]
            return (rows[0] if rows else None) if one else rows
        finally:
            conn.close()

    def execute(self, sql, params=()):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(self._sql(sql), params)
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    # ---------- setup ----------
    def init(self):
        conn = self._connect()
        try:
            cur = conn.cursor()
            for stmt in (MYSQL_SCHEMA if self.kind == "mysql" else SQLITE_SCHEMA):
                cur.execute(stmt)
            conn.commit()
        finally:
            conn.close()
        self._ensure_role_column()
        if not self.query("SELECT id FROM doctors LIMIT 1"):
            for d in SEED_DOCTORS:
                self.execute("INSERT INTO doctors (name, specialization, experience_years, available_days, "
                             "start_time, end_time, fee) VALUES (?,?,?,?,?,?,?)", d)


    def _ensure_role_column(self):
        """Upgrade older databases (created before the admin portal existed) by adding users.role."""
        if self.kind == "mysql":
            has = self.query("SHOW COLUMNS FROM users LIKE 'role'")
            ddl = "ALTER TABLE users ADD COLUMN role VARCHAR(10) DEFAULT 'user'"
        else:
            has = [c for c in self.query("PRAGMA table_info(users)") if c["name"] == "role"]
            ddl = "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'"
        if not has:
            self.execute(ddl)


db = Database()
