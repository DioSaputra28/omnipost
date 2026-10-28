import os
import threading
import time
import uuid

LOGIN_URLS = {
    "threads": "https://www.threads.com/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "facebook": "https://www.facebook.com/login/",
    "x": "https://x.com/login",
}

SESSIONS = {}
SESSION_TTL = 30 * 60

_lock = threading.Lock()

def _playwright():
    from playwright.sync_api import sync_playwright
    return sync_playwright

def _account_dir(account_id):
    from core.poster.base import account_dir
    return account_dir(account_id)

def start_login_session(platform, label, proxy="", headless=False):
    if platform not in LOGIN_URLS:
        raise ValueError(f"platform tidak dikenal: {platform}")
    from core.poster.base import launch_browser
    pw_mod = _playwright()
    token = uuid.uuid4().hex[:12]
    p = pw_mod().start()
    try:
        proxy_kw = {"server": proxy} if proxy else None
        browser = launch_browser(p, proxy_kw, headless=headless)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(LOGIN_URLS[platform], timeout=60000)
    except Exception:
        try:
            p.stop()
        except Exception:  # noqa: BLE001
            pass
        raise
    persistent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", "_login_" + token)
    with _lock:
        SESSIONS[token] = {
            "platform": platform, "label": label, "proxy": proxy,
            "p": p, "browser": browser, "ctx": ctx,
            "started": time.time(), "persistent_dir": persistent_dir,
        }
    return token

def _get(token):
    with _lock:
        s = SESSIONS.get(token)
    if not s:
        raise RuntimeError("sesi login tidak ketemu / sudah hangus")
    if time.time() - s["started"] > SESSION_TTL:
        cancel_login_session(token)
        raise RuntimeError("sesi login hangus (>30 menit)")
    return s

def cancel_login_session(token):
    with _lock:
        s = SESSIONS.pop(token, None)
    if not s:
        return
    try:
        s["browser"].close()
    except Exception:  # noqa: BLE001
        pass
    try:
        s["p"].stop()
    except Exception:  # noqa: BLE001
        pass

def finish_login_session(token, account_id):
    s = _get(token)
    from core.db import get_conn
    d = _account_dir(account_id)
    state_path = os.path.join(d, "storage_state.json")
    s["ctx"].storage_state(path=state_path)
    title = ""
    try:
        pages = s["ctx"].pages
        title = pages[0].title() if pages else ""
    except Exception:  # noqa: BLE001
        pass
    cancel_login_session(token)
    conn = get_conn()
    conn.execute("UPDATE social_accounts SET status='ok' WHERE id=?", (account_id,))
    conn.commit()
    conn.close()
    return {"state_path": state_path, "title": title}

def pending_login_token():
    with _lock:
        for tok, s in SESSIONS.items():
            if time.time() - s["started"] <= SESSION_TTL:
                return tok
    return None
