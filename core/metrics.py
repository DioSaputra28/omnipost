import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta

from core.db import get_conn

log = logging.getLogger("omnipost")

REFRESH_HOURS = 3
MAX_JOBS = 8
MAX_AGE_DAYS = 14

_NUM_RE = re.compile(r"([\d.,]+)\s*(k|rb|m|jt|b)?")


def _num(val):
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip().lower().replace("\u00a0", " ")
    s = s.replace("ribu", "rb").replace("juta", "jt")
    m = _NUM_RE.search(s)
    if not m:
        return 0
    raw, suf = m.group(1), m.group(2) or ""
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        parts = raw.split(",")
        raw = raw.replace(",", ".") if len(parts[-1]) <= 2 else raw.replace(",", "")
    try:
        v = float(raw)
    except ValueError:
        return 0
    mult = {"k": 1000, "rb": 1000, "m": 1000000, "jt": 1000000, "b": 1000000000}.get(suf, 1)
    return int(v * mult)


_EXTRACT_JS = """(() => {
    const body = document.body.innerText || '';
    const v = body.match(/([\\d.,]+\\s*(?:k|rb|m|jt|b)?)\\s+views?/i);
    const root = document.querySelector('div[data-pressable-container="true"]') || document.body;
    const pick = (prefix) => {
        for (const bt of root.querySelectorAll('[role="button"], button')) {
            const pEl = bt.querySelector('svg path');
            const d = pEl ? (pEl.getAttribute('d') || '') : '';
            if (d.indexOf(prefix) === 0) return (bt.innerText || '').trim();
        }
        return '';
    };
    return {
        views: v ? v[1] : '',
        likes: pick('M12 1C18.0654'),
        replies: pick('M16.5 2c-1.666'),
        reposts: pick('M4.516 6.999'),
        shares: pick('M7.247 1.499'),
    };
})()"""

_PROFILE_JS = """(() => {
    const out = [];
    document.querySelectorAll('div[data-pressable-container="true"]').forEach(a => {
        let href = '';
        a.querySelectorAll('a[href*="/post/"]').forEach(n => {
            const h = n.getAttribute('href') || '';
            if (!href && h.indexOf('/post/') >= 0) href = h;
        });
        out.push({href: href, text: (a.innerText || '')});
    });
    return out;
})()"""


def _save(job_id, post_url, data, error=""):
    conn = get_conn()
    conn.execute(
        """INSERT INTO post_metrics (job_id, post_url, views, likes, replies, reposts, shares, checked_at, error)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(job_id) DO UPDATE SET
             post_url=excluded.post_url, views=excluded.views, likes=excluded.likes,
             replies=excluded.replies, reposts=excluded.reposts, shares=excluded.shares,
             checked_at=excluded.checked_at, error=excluded.error""",
        (job_id, post_url or "", _num(data.get("views")), _num(data.get("likes")),
         _num(data.get("replies")), _num(data.get("reposts")), _num(data.get("shares")),
         datetime.now().isoformat(), error))
    conn.commit()
    conn.close()


def _hint(caption):
    text = re.sub(r"https?://\S+", "", caption or "")
    return re.sub(r"\s{2,}", " ", text).strip()[:30]


def _refresh_batch(account, jobs):
    from playwright.sync_api import sync_playwright
    from core.poster.base import launch_context

    with sync_playwright() as p:
        browser, ctx, _state = launch_context(p, account)
        try:
            page = ctx.new_page()
            username = (account.get("username") or "").strip().lstrip("@")
            posts = []
            if username:
                page.goto("https://www.threads.com/@" + username, timeout=60000)
                page.wait_for_timeout(5000)
                posts = page.evaluate(_PROFILE_JS) or []

            def _is_link_post(post):
                lines = [l.strip() for l in (post.get("text") or "").split("\n")[2:] if l.strip()]
                return bool(lines) and (lines[0].startswith("http") or "shopee" in lines[0][:30])

            used = set()
            used_urls = set()
            for job in jobs:
                hint = _hint(job["caption_hasil_ai"])
                url = (job.get("post_url") or "").strip()
                if url in used_urls:
                    url = ""
                elif url:
                    used_urls.add(url)
                if url:
                    for idx, post in enumerate(posts):
                        if "https://www.threads.com" + post["href"] == url:
                            used.add(idx)
                            break
                else:
                    avail = [(i, p) for i, p in enumerate(posts) if i not in used]
                    pick = None
                    for i, p in avail:
                        if hint and hint in (p.get("text") or "") and not _is_link_post(p):
                            pick = (i, p)
                            break
                    if not pick:
                        for i, p in avail:
                            if hint and hint in (p.get("text") or ""):
                                pick = (i, p)
                                break
                    if not pick:
                        for i, p in avail:
                            if not _is_link_post(p):
                                pick = (i, p)
                                break
                    if pick:
                        used.add(pick[0])
                        url = "https://www.threads.com" + pick[1]["href"]
                if url:
                    used_urls.add(url)
                if not url:
                    _save(job["id"], "", {}, "postingan tidak ketemu di profil")
                    log.info("metrics job %s: post tidak ketemu", job["id"])
                    continue
                page.goto(url, timeout=60000)
                page.wait_for_timeout(4500)
                data = page.evaluate(_EXTRACT_JS) or {}
                _save(job["id"], url, data)
                log.info("metrics job %s: views=%s likes=%s replies=%s reposts=%s shares=%s",
                         job["id"], data.get("views"), data.get("likes"),
                         data.get("replies"), data.get("reposts"), data.get("shares"))
        finally:
            browser.close()


def refresh_all(max_jobs=MAX_JOBS):
    from core.scheduler import LOCK

    cutoff = (datetime.now() - timedelta(hours=REFRESH_HOURS)).isoformat()
    oldest = (datetime.now() - timedelta(days=MAX_AGE_DAYS)).isoformat()
    conn = get_conn()
    rows = conn.execute(
        """SELECT j.id, j.account_id, j.caption_hasil_ai, j.posted_at, m.post_url
           FROM jobs j LEFT JOIN post_metrics m ON m.job_id = j.id
           JOIN social_accounts a ON a.id = j.account_id
           WHERE j.status = 'posted' AND j.posted_at IS NOT NULL
             AND lower(a.platform) = 'threads'
             AND j.posted_at > ?
             AND (m.checked_at IS NULL OR m.checked_at < ?)
           ORDER BY j.posted_at DESC LIMIT ?""",
        (oldest, cutoff, max_jobs)).fetchall()
    conn.close()
    if not rows:
        return 0

    grouped = defaultdict(list)
    for r in rows:
        grouped[r["account_id"]].append(dict(r))

    updated = 0
    for account_id, jobs in grouped.items():
        if not LOCK.acquire(blocking=False):
            log.info("metrics: skip akun %s (lock dipakai)", account_id)
            continue
        try:
            conn = get_conn()
            acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (account_id,)).fetchone()
            conn.close()
            if not acc:
                continue
            _refresh_batch(dict(acc), jobs)
            updated += len(jobs)
        except Exception as e:  # noqa: BLE001
            log.info("metrics akun %s gagal: %s", account_id, str(e)[:150])
        finally:
            LOCK.release()
    return updated


def refresh_jobs(job_ids):
    from core.scheduler import LOCK

    if not job_ids:
        return 0
    marks = ",".join("?" * len(job_ids))
    conn = get_conn()
    rows = conn.execute(
        f"""SELECT j.id, j.account_id, j.caption_hasil_ai, j.posted_at, m.post_url
            FROM jobs j LEFT JOIN post_metrics m ON m.job_id = j.id
            WHERE j.id IN ({marks})""", list(job_ids)).fetchall()
    conn.close()
    if not rows:
        return 0

    grouped = defaultdict(list)
    for r in rows:
        grouped[r["account_id"]].append(dict(r))

    updated = 0
    for account_id, jobs in grouped.items():
        if not LOCK.acquire(blocking=False):
            continue
        try:
            conn = get_conn()
            acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (account_id,)).fetchone()
            conn.close()
            if not acc:
                continue
            _refresh_batch(dict(acc), jobs)
            updated += len(jobs)
        except Exception as e:  # noqa: BLE001
            log.info("metrics akun %s gagal: %s", account_id, str(e)[:150])
        finally:
            LOCK.release()
    return updated

def refresh_job(job_id):
    from core.scheduler import LOCK

    conn = get_conn()
    job = conn.execute(
        "SELECT j.*, a.id AS aid FROM jobs j JOIN social_accounts a ON a.id = j.account_id WHERE j.id = ?",
        (job_id,)).fetchone()
    if not job:
        conn.close()
        return False, "job tidak ketemu"
    acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (job["account_id"],)).fetchone()
    conn.close()
    if not job["posted_at"]:
        return False, "postingan belum terbit, belum ada metrik"
    if (acc["platform"] or "").lower() != "threads":
        return False, "metrik baru tersedia untuk Threads"

    if not LOCK.acquire(blocking=False):
        return False, "sedang ada proses posting/scraping lain, coba lagi sebentar"
    try:
        _refresh_batch(dict(acc), [job])
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:200]
    finally:
        LOCK.release()
