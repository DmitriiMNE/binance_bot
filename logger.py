import sqlite3
from datetime import datetime

DB_FILE = 'db.sqlite'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        price REAL,
        quantity REAL,
        timestamp TEXT
    )''')
    conn.commit()
    conn.close()

def log_trade(action, price, quantity):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO trades (action, price, quantity, timestamp) VALUES (?, ?, ?, ?)',
              (action, price, quantity, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
