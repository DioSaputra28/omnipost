from playwright.sync_api import sync_playwright
from core.poster.base import launch_browser, launch_context, save_state_and_shot
from core.cookie_import import HOME_URLS

def check_session(account, save=True):
    with sync_playwright() as p:
        proxy = {"server": account["proxy"]} if account.get("proxy") else None
        browser = launch_browser(p, proxy)
        try:
            state_path = __import__("os").path.join(
                __import__("core.poster.base", fromlist=["account_dir"]).account_dir(account["id"]),
                "storage_state.json")
            import os as _os
            if not _os.path.exists(state_path):
                return False, "belum ada sesi tersimpan, klik Login Ulang"
            ctx = browser.new_context(storage_state=state_path,
                                      user_agent=account.get("user_agent") or None)
            try:
                page = ctx.new_page()
                page.goto(HOME_URLS[account["platform"]], timeout=45000)
                page.wait_for_timeout(4000)
                url = page.url.lower()
                if "login" in url or "signin" in url:
                    return False, "sesi mati, dilempar ke halaman login. Klik Login Ulang lalu export ulang."
                if save:
                    ctx.storage_state(path=state_path)
                try:
                    title = page.title()
                except Exception:  # noqa: BLE001
                    title = ""
                return True, "sesi hidup (%s)" % (title[:60] if title else "OK")
            finally:
                ctx.close()
        finally:
            browser.close()

def refresh_all_sessions(max_age_hours=24):
    from core.db import get_conn
    from datetime import datetime, timedelta
    conn = get_conn()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(social_accounts)").fetchall()]
    if "last_check_at" not in cols:
        conn.execute("ALTER TABLE social_accounts ADD COLUMN last_check_at TEXT DEFAULT ''")
        conn.commit()
    if "check_error" not in cols:
        conn.execute("ALTER TABLE social_accounts ADD COLUMN check_error TEXT DEFAULT ''")
        conn.commit()
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    rows = conn.execute(
        "SELECT * FROM social_accounts WHERE status NOT IN ('paused','waiting-login','checking') "
        "AND (last_check_at IS NULL OR last_check_at = '' OR last_check_at < ?)", (cutoff,)).fetchall()
    conn.close()
    for acc in rows:
        a = dict(acc)
        try:
            ok, msg = check_session(a, save=True)
            status = "ok" if ok else "session-expired"
            err = "" if ok else msg
        except Exception as e:  # noqa: BLE001
            status, err, msg = "session-expired", str(e)[:300], str(e)[:300]
            ok = False
        conn = get_conn()
        new_status = a["status"] if ok and a["status"] in ("ok", "cookies-ok") else ("ok" if ok else "session-expired")
        conn.execute("UPDATE social_accounts SET status=?, last_check_at=?, check_error=? WHERE id=?",
                     (new_status,
                      datetime.now().isoformat(), err, a["id"]))
        conn.commit()
        conn.close()
