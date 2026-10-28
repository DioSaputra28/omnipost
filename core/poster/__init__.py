from playwright.sync_api import sync_playwright
from core.poster.base import launch_context, save_state_and_shot

def post(account, caption, job_id):
    with sync_playwright() as p:
        browser, ctx, state_path = launch_context(p, account)
        try:
            page = ctx.new_page()
            page.goto("https://www.threads.net/", timeout=60000)
            page.wait_for_timeout(3000)
            if "/login" in page.url:
                raise RuntimeError("sesi mati, dilempar ke halaman login. Klik Login Ulang di detail akun.")
            page.keyboard.press("r")
            page.wait_for_timeout(2000)
            page.fill('div[role="textbox"]', caption)
            page.wait_for_timeout(1000)
            page.keyboard.press("Control+Enter")
            page.wait_for_timeout(4000)
            shot = save_state_and_shot(ctx, state_path, account["id"], job_id)
            return shot
        finally:
            browser.close()

def post_to_platform(account, caption, job_id):
    plat = (account.get("platform") or "").lower()
    if plat == "threads":
        return post(account, caption, job_id)
    if plat == "instagram":
        from core.poster import instagram
        return instagram.post(account, caption, job_id)
    if plat in ("fb", "facebook"):
        from core.poster import facebook
        return facebook.post(account, caption, job_id)
    if plat in ("x", "twitter"):
        from core.poster import twitter
        return twitter.post(account, caption, job_id)
    raise ValueError(f"platform tidak dikenal: {plat}")
