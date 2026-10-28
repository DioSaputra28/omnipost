import os
import random
import threading
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from core.db import get_conn
from core.ai import generate_story
from core.poster import post_to_platform

LOCK = threading.Lock()
DEDUP_DAYS = int(os.getenv("DEDUP_DAYS", "14"))

def _pick_product(account_id):
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=DEDUP_DAYS)).isoformat()
    rows = conn.execute(
        """SELECT p.* FROM products p WHERE p.aktif = 1 AND p.id NOT IN
           (SELECT product_id FROM jobs WHERE account_id = ? AND status = 'posted'
            AND posted_at IS NOT NULL AND posted_at > ?)
           ORDER BY RANDOM() LIMIT 1""",
        (account_id, cutoff)).fetchone()
    conn.close()
    return rows

def _get_persona(account_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM personas WHERE account_id = ? LIMIT 1", (account_id,)).fetchone()
    conn.close()
    return row

def run_job_for_account(account_id, manual_product_id=None):
    with LOCK:
        conn = get_conn()
        acc = conn.execute("SELECT * FROM social_accounts WHERE id = ?", (account_id,)).fetchone()
        conn.close()
        if not acc:
            return None, "akun tidak ketemu"

        prod = None
        if manual_product_id:
            conn = get_conn()
            prod = conn.execute("SELECT * FROM products WHERE id = ?", (manual_product_id,)).fetchone()
            conn.close()
        else:
            prod = _pick_product(account_id)
        if not prod:
            return None, "tidak ada produk tersedia (habis / kena dedup 14 hari)"

        persona = _get_persona(account_id)
        if persona:
            caption = generate_story(persona["system_prompt"], persona["gaya_bahasa"],
                                     persona["contoh_cerita"], prod["nama"],
                                     prod["deskripsi"], prod["link_shopee"])
        else:
            caption = f"Hari ini nemu {prod['nama']} yang bagus banget, ternyata belinya di sini {prod['link_shopee']}"

        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO jobs (account_id, product_id, caption_hasil_ai, status, scheduled_at) VALUES (?,?,?, 'queued', ?)",
            (account_id, prod["id"], caption, datetime.now().isoformat()))
        job_id = cur.lastrowid
        conn.commit()
        conn.close()

        try:
            shot = post_to_platform(dict(acc), caption, job_id)
            conn = get_conn()
            conn.execute("UPDATE jobs SET status='posted', posted_at=?, screenshot_path=? WHERE id = ?",
                         (datetime.now().isoformat(), shot, job_id))
            conn.execute("UPDATE social_accounts SET last_post_at=?, status='ok' WHERE id = ?",
                         (datetime.now().isoformat(), account_id))
            conn.commit()
            conn.close()
            return job_id, None
        except Exception as e:  # noqa: BLE001
            err = str(e)
            conn = get_conn()
            conn.execute("UPDATE jobs SET status='failed', error=? WHERE id = ?", (err, job_id))
            conn.execute("UPDATE social_accounts SET status='error' WHERE id = ?", (account_id,))
            conn.commit()
            conn.close()
            return job_id, err

def tick():
    now = datetime.now()
    conn = get_conn()
    accs = conn.execute("SELECT * FROM social_accounts WHERE status != 'paused'").fetchall()
    conn.close()
    for acc in accs:
        if not (acc["active_hour_start"] <= now.hour < acc["active_hour_end"]):
            continue
        last = acc["last_post_at"]
        interval_h = 24.0 / max(acc["posts_per_day"] or 3, 1)
        jitter_min = random.randint(5, 25)
        due_at = (datetime.fromisoformat(last) + timedelta(hours=interval_h, minutes=jitter_min)) if last else now
        if now >= due_at:
            try:
                run_job_for_account(acc["id"])
            except Exception:  # noqa: BLE001
                pass

_scheduler = None

def start_scheduler():
    global _scheduler
    if _scheduler:
        return _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(tick, "interval", minutes=5)
    _scheduler.start()
    return _scheduler
