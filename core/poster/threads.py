from playwright.sync_api import sync_playwright
from core.poster.base import launch_context

def login_check(account):
    with sync_playwright() as p:
        browser, ctx, state_path = launch_context(p, account)
        try:
            page = ctx.new_page()
            page.goto("https://www.threads.com/", timeout=60000)
            page.wait_for_timeout(3000)
            if "/login" in page.url:
                raise RuntimeError("sesi mati, dilempar ke halaman login. Klik Login Ulang di detail akun.")
            ctx.storage_state(path=state_path)
            return True
        finally:
            browser.close()
