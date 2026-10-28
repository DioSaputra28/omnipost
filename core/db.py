import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db.sqlite")

SCHEMA = """
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    label TEXT NOT NULL,
    proxy TEXT,
    posts_per_day INTEGER DEFAULT 3,
    active_hour_start INTEGER DEFAULT 7,
    active_hour_end INTEGER DEFAULT 21,
    status TEXT DEFAULT 'new',
    last_post_at TEXT,
    login_token TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    last_check_at TEXT DEFAULT '',
    check_error TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES social_accounts(id) ON DELETE CASCADE,
    nama TEXT NOT NULL,
    gaya_bahasa TEXT DEFAULT '',
    system_prompt TEXT NOT NULL,
    contoh_cerita TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    link_shopee TEXT NOT NULL,
    deskripsi TEXT DEFAULT '',
    kategori TEXT DEFAULT '',
    aktif INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES social_accounts(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    caption_hasil_ai TEXT DEFAULT '',
    status TEXT DEFAULT 'queued',
    scheduled_at TEXT,
    posted_at TEXT,
    screenshot_path TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
"""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(social_accounts)").fetchall()]
    for col in ["user_agent", "last_check_at", "check_error", "login_token"]:
        if col not in cols:
            conn.execute(f"ALTER TABLE social_accounts ADD COLUMN {col} TEXT DEFAULT ''")
            conn.commit()
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ai_base_url', 'https://api.openai.com/v1')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ai_api_key', '')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ai_model', 'gpt-4o-mini')")
    conn.commit()
    conn.close()

def get_setting(key, default=""):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()
