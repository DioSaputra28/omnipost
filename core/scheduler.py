import logging
import os
import random
import threading
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from core.db import get_conn, get_setting
from core.ai import (generate_story, generate_daily_story, StoryValidationError, STORY_SHAPES,
                     hook_of, find_duplicate_hook, DAILY_TOPICS)
from core.poster import post_to_platform, add_link_reply

log = logging.getLogger("omnipost")

LOCK = threading.Lock()
DEDUP_DAYS = int(os.getenv("DEDUP_DAYS", "14"))

def _num_terjual(val):
    from core.metrics import _num
    try:
        return _num(val)
    except Exception:  # noqa: BLE001
        return 0

def _score(p, max_komisi, max_terjual):
    import math
    komisi = float(p["komisi"] or 0)
    terjual = _num_terjual(p["terjual"] or "")
    k = (komisi / max_komisi) if max_komisi > 0 else 0
    t = (math.log(1 + terjual) / math.log(1 + max_terjual)) if max_terjual > 0 else 0
    return komisi * 0.6 * k + math.log(1 + terjual) * 0.4 * t

def _pick_product(account_id):
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=DEDUP_DAYS)).isoformat()
    rows = conn.execute(
        """SELECT p.* FROM products p WHERE p.aktif = 1 AND p.id NOT IN
           (SELECT product_id FROM jobs WHERE account_id = ? AND status = 'posted'
            AND product_id IS NOT NULL AND posted_at IS NOT NULL AND posted_at > ?)
           ORDER BY p.id DESC""",
        (account_id, cutoff)).fetchall()
    last = conn.execute(
        """SELECT p.kategori FROM jobs j JOIN products p ON p.id = j.product_id
           WHERE j.account_id = ? AND j.status = 'posted'
           ORDER BY j.id DESC LIMIT 1""", (account_id,)).fetchone()
    conn.close()
    if not rows:
        return None
    last_cat = (last["kategori"] if last else "") or ""
    if last_cat:
        rotated = [p for p in rows if (p["kategori"] or "") != last_cat]
        if rotated:
            rows = rotated
    max_komisi = max(float(p["komisi"] or 0) for p in rows)
    max_terjual = max(_num_terjual(p["terjual"] or "") for p in rows)
    return max(rows, key=lambda p: _score(p, max_komisi, max_terjual))

def _pick_post_type(acc):
    try:
        ratio = max(0, min(100, int(acc["promo_ratio"] if "promo_ratio" in acc.keys() else 70)))
    except (TypeError, ValueError):
        ratio = 70
    conn = get_conn()
    rows = conn.execute(
        "SELECT post_type FROM jobs WHERE account_id=? AND status='posted' ORDER BY id DESC LIMIT 2",
        (acc["id"],)).fetchall()
    conn.close()
    types = [(r["post_type"] or "promo") for r in rows]
    if len(types) == 2 and types[0] == types[1] == "promo":
        return "story"
    if len(types) == 2 and types[0] == types[1] == "story":
        return "promo"
    return "promo" if random.randint(1, 100) <= ratio else "story"

def _pick_shape(account_id, winning=None):
    conn = get_conn()
    rows = conn.execute(
        "SELECT story_shape FROM jobs WHERE account_id=? AND status='posted' AND post_type='promo' "
        "AND story_shape != '' ORDER BY id DESC LIMIT 2", (account_id,)).fetchall()
    conn.close()
    recent = {r["story_shape"] for r in rows}
    pool = [x for x in STORY_SHAPES if x not in recent] or list(STORY_SHAPES)
    hot = [x for x in (winning or []) if x in pool]
    return random.choice(hot or pool)

DEDUP_HOOK_DAYS = int(os.getenv("DEDUP_HOOK_DAYS", "14"))

TOPIC_ROTATE_DAYS = int(os.getenv("TOPIC_ROTATE_DAYS", "30"))
BAIT_MIN_PER_WEEK = int(os.getenv("BAIT_MIN_PER_WEEK", "2"))
BAIT_MAX_PER_WEEK = int(os.getenv("BAIT_MAX_PER_WEEK", "3"))

def _bait_due(account_id):
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    conn = get_conn()
    used = conn.execute(
        "SELECT COUNT(*) c FROM jobs WHERE account_id=? AND status='posted' AND has_bait=1 "
        "AND posted_at IS NOT NULL AND posted_at > ?", (account_id, cutoff)).fetchone()["c"]
    conn.close()
    if used >= BAIT_MAX_PER_WEEK:
        return False, used
    if used < BAIT_MIN_PER_WEEK:
        return True, used
    return random.random() < 0.5, used

def _pick_topic(account_id):
    cutoff = (datetime.now() - timedelta(days=TOPIC_ROTATE_DAYS)).isoformat()
    conn = get_conn()
    used = {r["topic"] for r in conn.execute(
        "SELECT topic FROM topic_history WHERE account_id=? AND used_at > ?", (account_id, cutoff)).fetchall()}
    pool = [t for t in DAILY_TOPICS if t not in used] or list(DAILY_TOPICS)
    topic = random.choice(pool)
    conn.execute("INSERT INTO topic_history (account_id, topic, used_at) VALUES (?,?,?)",
                 (account_id, topic, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return topic

def _persona_ctx(persona):
    if not persona:
        return {"profil": "", "niche": "", "larangan": "", "contoh_buruk": "", "banned": []}
    def g(key):
        try:
            return persona[key] or ""
        except (IndexError, KeyError):
            return ""
    bans = [x.strip() for x in __import__("re").split(r"[,\n;]+", g("larangan")) if x.strip()]
    return {"profil": g("profil"), "niche": g("niche"), "larangan": g("larangan"),
            "contoh_buruk": g("contoh_buruk"), "banned": bans}

def _recent_hooks(account_id, days=DEDUP_HOOK_DAYS):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_conn()
    rows = conn.execute(
        "SELECT hook FROM jobs WHERE account_id=? AND hook != '' AND posted_at IS NOT NULL "
        "AND posted_at > ? ORDER BY id DESC LIMIT 30", (account_id, cutoff)).fetchall()
    conn.close()
    return [r["hook"] for r in rows]

def _get_persona(account_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM personas WHERE account_id = ? LIMIT 1", (account_id,)).fetchone()
    conn.close()
    return row

def run_job_for_account(account_id, manual_product_id=None, force_type=None):
    with LOCK:
        conn = get_conn()
        acc = conn.execute("SELECT * FROM social_accounts WHERE id = ?", (account_id,)).fetchone()
        conn.close()
        if not acc:
            return None, "akun tidak ketemu"

        ptype = force_type if force_type in ("promo", "story") else _pick_post_type(acc)
        if ptype == "story" and manual_product_id:
            ptype = "promo"

        prod = None
        if ptype == "promo":
            if manual_product_id:
                conn = get_conn()
                prod = conn.execute("SELECT * FROM products WHERE id = ?", (manual_product_id,)).fetchone()
                conn.close()
            else:
                prod = _pick_product(account_id)
            if not prod:
                if force_type == "promo":
                    return None, "tidak ada produk tersedia (habis / kena dedup 14 hari)"
                ptype = "story"

        persona = _get_persona(account_id)
        part1 = part2 = bait = ""
        shape = ""
        link_state = ""
        if ptype == "promo":
            autolink = (get_setting("autolink_enabled", "0") or "0") == "1"
            link_state = "pending" if autolink else "inline"
            recent_hooks = _recent_hooks(account_id)
            from core.metrics import winning_angles
            winning = winning_angles(account_id)
            shape = _pick_shape(account_id, winning)
            pctx = _persona_ctx(persona)
            if persona:
                try:
                    part1 = part2 = bait = ""
                    bait_ok, bait_count = _bait_due(account_id)
                    for attempt in range(3):
                        shape = _pick_shape(account_id, winning)
                        p1, p2, bt = generate_story(
                            persona["system_prompt"], persona["gaya_bahasa"], persona["contoh_cerita"],
                            prod["nama"], prod["deskripsi"], prod["link_shopee"],
                            shape=shape, avoid_hooks=recent_hooks,
                            profil=pctx["profil"], niche=pctx["niche"],
                            larangan=pctx["larangan"], contoh_buruk=pctx["contoh_buruk"],
                            extra_banned=pctx["banned"], winning=winning)
                        dup = find_duplicate_hook(hook_of(p1), recent_hooks)
                        if not dup:
                            part1, part2, bait = p1, p2, (bt if bait_ok else "")
                            break
                        log.info("hook mirip (percobaan %d): %r ~ %r", attempt + 1, hook_of(p1), dup)
                        part1, part2, bait = p1, p2, (bt if bait_ok else "")
                    if part1 and find_duplicate_hook(hook_of(part1), recent_hooks):
                        err = "hook mirip postingan 14 hari terakhir: %r" % hook_of(part1)
                        conn = get_conn()
                        cur = conn.execute(
                            "INSERT INTO jobs (account_id, product_id, caption_hasil_ai, status, scheduled_at, "
                            "post_type, link_status, error, hook, story_shape) "
                            "VALUES (?,?,?, 'failed', ?, 'promo', 'none', ?, ?, ?)",
                            (account_id, prod["id"], part1, datetime.now().isoformat(), err,
                             hook_of(part1), shape))
                        jid = cur.lastrowid
                        conn.commit()
                        conn.close()
                        log.warning("job %s dibatalkan: %s", jid, err)
                        return jid, err
                except StoryValidationError as ve:
                    err = "validasi konten gagal: " + "; ".join(ve.errors)
                    conn = get_conn()
                    cur = conn.execute(
                        "INSERT INTO jobs (account_id, product_id, caption_hasil_ai, status, scheduled_at, "
                        "post_type, link_status, error) VALUES (?,?,?, 'failed', ?, 'promo', 'none', ?)",
                        (account_id, prod["id"], "", datetime.now().isoformat(), err))
                    jid = cur.lastrowid
                    conn.commit()
                    conn.close()
                    log.warning("job %s dibatalkan: %s", jid, err)
                    return jid, err
            if not part1:
                part1 = f"Hari ini nemu {prod['nama']} yang bagus banget."
                part2 = f"Ternyata belinya di sini."
                bait = ""
            joined = part1
            if part2:
                joined += "\n\n" + part2
            if not autolink:
                joined += "\n" + prod["link_shopee"]
            caption = joined
        else:
            link_state = "none"
            if persona:
                pctx = _persona_ctx(persona)
                caption = generate_daily_story(persona["system_prompt"], persona["gaya_bahasa"],
                                               persona["contoh_cerita"], topik=_pick_topic(account_id),
                                               profil=pctx["profil"], niche=pctx["niche"],
                                               larangan=pctx["larangan"])
            else:
                caption = "Lagi pengen cerita random aja hari ini. Kalian gimana, hari ini berjalan lancar?"
            part1 = caption

        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO jobs (account_id, product_id, caption_hasil_ai, status, scheduled_at, post_type, "
            "part1, part2, reply_bait, link_status, story_shape, hook, has_bait) "
            "VALUES (?,?,?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (account_id, (prod["id"] if prod else None), caption, datetime.now().isoformat(), ptype,
             part1, part2, bait, link_state, shape, hook_of(part1), 1 if bait else 0))
        job_id = cur.lastrowid
        conn.commit()
        conn.close()

        try:
            shot = post_to_platform(dict(acc), caption, job_id,
                                    include_link=link_state == "inline",
                                    part1=part1, part2=part2, reply_bait=bait)
            conn = get_conn()
            conn.execute("UPDATE jobs SET status='posted', posted_at=?, screenshot_path=?, link_status=? WHERE id = ?",
                         (datetime.now().isoformat(), shot, link_state, job_id))
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
           FROM jobs j LEFT JOIN products p ON p.id = j.product_id
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
               FROM jobs j LEFT JOIN products p ON p.id = j.product_id
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
