from playwright.sync_api import sync_playwright
from core.poster.base import launch_context, save_state_and_shot

def post(account, caption, job_id):
    with sync_playwright() as p:
        browser, ctx, state_path = launch_context(p, account)
        try:
            page = ctx.new_page()
            page.goto("https://www.facebook.com/", timeout=60000)
            page.wait_for_timeout(4000)
            box = page.locator('div[role="textbox"]').first
            box.click()
            page.wait_for_timeout(1000)
            box.fill(caption)
            page.wait_for_timeout(1000)
            page.keyboard.press("Control+Enter")
            page.wait_for_timeout(4000)
            return save_state_and_shot(ctx, state_path, account["id"], job_id)
        finally:
            browser.close()
