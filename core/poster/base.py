import glob as _glob
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

HEADLESS = os.getenv("BROWSER_HEADLESS", "true") == "true"
STORAGE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage")

def _find_chrome():
    cands = sorted(_glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")), reverse=True)
    for c in cands:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    for c in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome", "/opt/google/chrome/chrome"]:
        if os.path.isfile(c):
            return c
    return None

def launch_browser(p, proxy=None, headless=None):
    use_headless = HEADLESS if headless is None else headless
    try:
        return p.chromium.launch(headless=use_headless, proxy=proxy)
    except Exception as e:  # noqa: BLE001
        if "Executable doesn't exist" not in str(e):
            raise
        exe = _find_chrome()
        if not exe:
            raise RuntimeError("Chromium belum terinstall. Jalankan: .venv/bin/python -m playwright install chromium (butuh internet ~150MB). Kalau gagal download, install chromium sistem: sudo apt install chromium.")
        return p.chromium.launch(headless=use_headless, proxy=proxy, executable_path=exe)

def account_dir(account_id):
    d = os.path.join(STORAGE_ROOT, str(account_id))
    os.makedirs(os.path.join(d, "shots"), exist_ok=True)
    return d

def launch_context(p, account):
    proxy = None
    if account.get("proxy"):
        proxy = {"server": account["proxy"]}
    browser = launch_browser(p, proxy)
    state_path = os.path.join(account_dir(account["id"]), "storage_state.json")
    kwargs = {}
    if os.path.exists(state_path):
        kwargs["storage_state"] = state_path
    else:
        raise RuntimeError(f"akun {account.get('label','?')} belum login: tidak ada storage_state.json, klik Login Ulang dulu")
    if account.get("user_agent"):
        kwargs["user_agent"] = account["user_agent"]
    ctx = browser.new_context(**kwargs)
    if not account.get("username"):
        try:
            pg = ctx.new_page()
            pg.goto("https://www.threads.com/", timeout=45000)
            pg.wait_for_timeout(4000)
            for a in pg.locator('a[href^="/@"]').all()[:20]:
                try:
                    href = a.get_attribute("href") or ""
                    if href.startswith("/@") and len(href) > 2:
                        from core.db import get_conn as _gc
                        _c = _gc()
                        _c.execute("UPDATE social_accounts SET username=? WHERE id=?",
                                   (href[2:].split("/")[0], account["id"]))
                        _c.commit()
                        _c.close()
                        break
                except Exception:  # noqa: BLE001
                    pass
            pg.close()
        except Exception:  # noqa: BLE001
            pass
    return browser, ctx, state_path

def save_state_and_shot(ctx, state_path, account_id, job_id):
    import re as _re
    ctx.storage_state(path=state_path)
    pages = ctx.pages
    if pages:
        try:
            url = pages[0].url
        except Exception:  # noqa: BLE001
            url = ""
        if _re.search(r"/@[^/]+$", url.rstrip("/")) or "/t/" in url:
            shot = os.path.join(account_dir(account_id), "shots", f"{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            pages[0].screenshot(path=shot)
            return shot
    for pg in pages:
        try:
            pg.bring_to_front()
            pg.wait_for_timeout(1500)
            shot = os.path.join(account_dir(account_id), "shots", f"{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            pg.screenshot(path=shot)
            return shot
        except Exception:  # noqa: BLE001
            pass
    shot = os.path.join(account_dir(account_id), "shots", f"{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    pages[0].screenshot(path=shot) if pages else None
    return shot
