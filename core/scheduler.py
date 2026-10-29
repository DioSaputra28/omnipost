import os
import random
import threading
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from core.db import get_conn, get_setting
from core.ai import generate_story
from core.poster import post_to_platform, add_link_reply

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

        autolink = (get_setting("autolink_enabled", "0") or "0") == "1"
        try:
            shot = post_to_platform(dict(acc), caption, job_id, include_link=not autolink)
            conn = get_conn()
            conn.execute("UPDATE jobs SET status='posted', posted_at=?, screenshot_path=?, link_status=? WHERE id = ?",
                         (datetime.now().isoformat(), shot, "pending" if autolink else "inline", job_id))
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

def _backoff_ok(acc, now):
    err = (acc["check_error"] if "check_error" in acc.keys() else "") or ""
    last_check = (acc["last_check_at"] if "last_check_at" in acc.keys() else "") or ""
    if acc["status"] not in ("session-expired", "error") or not last_check:
        return True
    try:
        mins = (now - datetime.fromisoformat(last_check)).total_seconds() / 60
    except ValueError:
        return True
    fails = err.count("sesi mati") + err.count("gagal") + 1
    wait = min(30 * (2 ** min(fails, 5)), 720)
    return mins >= wait

def tick():
    now = datetime.now()
    conn = get_conn()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(social_accounts)").fetchall()]
    if "last_check_at" not in cols:
        conn.execute("ALTER TABLE social_accounts ADD COLUMN last_check_at TEXT DEFAULT ''")
        conn.commit()
    if "check_error" not in cols:
        conn.execute("ALTER TABLE social_accounts ADD COLUMN check_error TEXT DEFAULT ''")
        conn.commit()
    accs = conn.execute("SELECT * FROM social_accounts WHERE status NOT IN ('paused','waiting-login','checking','session-expired')").fetchall()
    conn.close()
    for acc in accs:
        if not (acc["active_hour_start"] <= now.hour < acc["active_hour_end"]):
            continue
        if not _backoff_ok(acc, now):
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

def autolink_check():
    if (get_setting("autolink_enabled", "0") or "0") != "1":
        return 0
    try:
        metric = get_setting("autolink_metric", "views") or "views"
        threshold = int(get_setting("autolink_threshold", "100") or 100)
        window_h = int(get_setting("autolink_window_hours", "24") or 24)
    except (TypeError, ValueError):
        metric, threshold, window_h = "views", 100, 24

    conn = get_conn()
    rows = conn.execute(
        """SELECT j.id, j.account_id, j.posted_at, p.link_shopee, m.post_url, m.views, m.likes, m.checked_at
           FROM jobs j JOIN products p ON p.id = j.product_id
           LEFT JOIN post_metrics m ON m.job_id = j.id
           WHERE j.status = 'posted' AND j.link_status = 'pending'""").fetchall()
    conn.close()

    stale = []
    fresh_cut = (datetime.now() - timedelta(minutes=30)).isoformat()
    for r in rows:
        if not r["post_url"] or not (r["checked_at"] or "") or (r["checked_at"] or "") < fresh_cut:
            stale.append(r["id"])
    if stale:
        from core.metrics import refresh_jobs
        refresh_jobs(stale)
        conn = get_conn()
        rows = conn.execute(
            """SELECT j.id, j.account_id, j.posted_at, p.link_shopee, m.post_url, m.views, m.likes, m.checked_at
               FROM jobs j JOIN products p ON p.id = j.product_id
               LEFT JOIN post_metrics m ON m.job_id = j.id
               WHERE j.status = 'posted' AND j.link_status = 'pending'""").fetchall()
        conn.close()

    done = 0
    for r in rows:
        try:
            posted_at = datetime.fromisoformat(r["posted_at"])
        except (TypeError, ValueError):
            continue
        if (datetime.now() - posted_at) > timedelta(hours=window_h):
            conn = get_conn()
            conn.execute("UPDATE jobs SET link_status='expired' WHERE id=?", (r["id"],))
            conn.commit()
            conn.close()
            continue
        value = (r["views"] or 0) if metric == "views" else (r["likes"] or 0)
        if value < threshold:
            continue
        if not r["post_url"]:
            continue
        if not LOCK.acquire(blocking=False):
            return done
        try:
            conn = get_conn()
            acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (r["account_id"],)).fetchone()
            conn.close()
            if not acc:
                continue
            ok = add_link_reply(dict(acc), r["post_url"], r["link_shopee"], r["id"])
            if ok:
                conn = get_conn()
                conn.execute("UPDATE jobs SET link_status='added', link_added_at=? WHERE id=?",
                             (datetime.now().isoformat(), r["id"]))
                conn.commit()
                conn.close()
                done += 1
        finally:
            LOCK.release()
    return done

_scheduler = None

def start_scheduler():
    global _scheduler
    if _scheduler:
        return _scheduler
    from core.session_guard import refresh_all_sessions
    from core.metrics import refresh_all as refresh_metrics
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(tick, "interval", minutes=5)
    _scheduler.add_job(refresh_all_sessions, "interval", hours=6, kwargs={"max_age_hours": 20})
    _scheduler.add_job(refresh_metrics, "interval", hours=3)
    _scheduler.add_job(autolink_check, "interval", minutes=30)
    _scheduler.start()
    return _scheduler
