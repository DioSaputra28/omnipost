from playwright.sync_api import sync_playwright
from core.poster.base import launch_context, save_state_and_shot

def post(account, caption, job_id):
    with sync_playwright() as p:
        browser, ctx, state_path = launch_context(p, account)
        try:
            page = ctx.new_page()
            page.goto("https://x.com/compose/post", timeout=60000)
            page.wait_for_timeout(4000)
            if "/login" in page.url:
                raise RuntimeError("sesi mati, dilempar ke halaman login. Klik Login Ulang di detail akun.")
            box = page.locator('div[role="textbox"]').first
            box.fill(caption)
            page.wait_for_timeout(1000)
            page.get_by_test_id("tweetButton").click()
            page.wait_for_timeout(4000)
            return save_state_and_shot(ctx, state_path, account["id"], job_id)
        finally:
            browser.close()
