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

def launch_browser(p, proxy=None):
    try:
        return p.chromium.launch(headless=HEADLESS, proxy=proxy)
    except Exception as e:  # noqa: BLE001
        if "Executable doesn't exist" not in str(e):
            raise
        exe = _find_chrome()
        if not exe:
            raise RuntimeError("Chromium belum terinstall. Jalankan: .venv/bin/python -m playwright install chromium (butuh internet ~150MB). Kalau gagal download, install chromium sistem: sudo apt install chromium.")
        return p.chromium.launch(headless=HEADLESS, proxy=proxy, executable_path=exe)

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
    return browser, ctx, state_path

def save_state_and_shot(ctx, state_path, account_id, job_id):
    ctx.storage_state(path=state_path)
    shot = os.path.join(account_dir(account_id), "shots", f"{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    ctx.pages[0].screenshot(path=shot) if ctx.pages else None
    return shot
