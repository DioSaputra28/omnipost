from playwright.sync_api import sync_playwright
from core.poster.base import launch_context, save_state_and_shot

def login_check(account):
    with sync_playwright() as p:
        browser, ctx, state_path = launch_context(p, account)
        try:
            page = ctx.new_page()
            page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
            page.wait_for_timeout(3000)
            if "login" in page.url:
                u = account.get("username") or ""
                pw = account.get("password_enc") or ""
                if not u or not pw:
                    raise RuntimeError("butuh username+password untuk login IG pertama kali")
                page.fill('input[name="username"]', u)
                page.fill('input[name="password"]', pw)
                page.keyboard.press("Enter")
                page.wait_for_timeout(6000)
            ctx.storage_state(path=state_path)
            return True
        finally:
            browser.close()

def post(account, caption, job_id):
    with sync_playwright() as p:
        browser, ctx, state_path = launch_context(p, account)
        try:
            page = ctx.new_page()
            page.goto("https://www.instagram.com/", timeout=60000)
            page.wait_for_timeout(4000)
            page.keyboard.press("p")
            page.wait_for_timeout(2000)
            box = page.locator('div[role="textbox"]').first
            box.fill(caption)
            page.wait_for_timeout(1000)
            page.keyboard.press("Control+Enter")
            page.wait_for_timeout(4000)
            return save_state_and_shot(ctx, state_path, account["id"], job_id)
        finally:
            browser.close()
