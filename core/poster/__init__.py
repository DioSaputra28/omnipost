from playwright.sync_api import sync_playwright
from core.poster.base import launch_context, save_state_and_shot

def _debug_shot(ctx, account_id, job_id, tag):
    import os
    from datetime import datetime
    from core.poster.base import account_dir
    path = os.path.join(account_dir(account_id), "shots", f"{job_id}_debug_{tag}_{datetime.now().strftime('%H%M%S')}.png")
    try:
        ctx.pages[0].screenshot(path=path)
    except Exception:  # noqa: BLE001
        pass
    return path

def post(account, caption, job_id):
    import re
    with sync_playwright() as p:
        browser, ctx, state_path = launch_context(p, account)
        try:
            page = ctx.new_page()
            page.goto("https://www.threads.com/", timeout=60000)
            page.wait_for_timeout(4000)
            if "/login" in page.url:
                raise RuntimeError("sesi mati, dilempar ke halaman login. Klik Login Ulang di detail akun.")
            opened = False
            for sel in [
                'a[href="/compose"]', 'a[href*="compose"]',
                'button:has-text("Start a thread")', 'button:has-text("Mulai")',
                'div:has-text("Start a thread")',
            ]:
                try:
                    loc = page.locator(sel).first
                    if loc.count() and loc.is_visible():
                        loc.click()
                        opened = True
                        break
                except Exception:  # noqa: BLE001
                    pass
            if not opened:
                for txt in ["What's new?", "What’s new?", "New thread"]:
                    try:
                        loc = page.get_by_text(txt, exact=False).first
                        if loc.count() and loc.is_visible():
                            loc.click()
                            opened = True
                            break
                    except Exception:  # noqa: BLE001
                        pass
            if not opened:
                page.keyboard.press("r")
            page.wait_for_timeout(2500)
            box = None
            for sel in ['div[role="textbox"]', '[contenteditable="true"]',
                        'div[aria-label*="thread" i]', 'div[aria-label*="Start" i]']:
                try:
                    loc = page.locator(sel).first
                    loc.wait_for(state="visible", timeout=8000)
                    box = loc
                    break
                except Exception:  # noqa: BLE001
                    pass
            if not box:
                _debug_shot(ctx, account["id"], job_id, "no-box")
                raise RuntimeError(
                    "composer Threads tidak ketemu (UI berubah?). URL saat ini: %s. "
                    "Screenshot debug tersimpan di storage/%s/shots/ (file _debug_no-box). "
                    "Buka manual di browser, lihat tombol/composer barunya kayak apa." % (page.url, account["id"]))
            box.click()
            page.wait_for_timeout(500)
            try:
                box.fill("")
            except Exception:  # noqa: BLE001
                pass
            box.fill(caption)
            page.wait_for_timeout(1500)
            try:
                if page.locator('text="Who can reply and quote"').count():
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(800)
            except Exception:  # noqa: BLE001
                pass
            dialog = None
            for sel in ['div[role="dialog"]', 'div[aria-modal="true"]']:
                try:
                    loc = page.locator(sel).first
                    if loc.count() and loc.is_visible():
                        dialog = loc
                        break
                except Exception:  # noqa: BLE001
                    pass
            posted = False
            scope = dialog if dialog else page
            try:
                cands = scope.locator("button").filter(has_text=re.compile(r"^\s*Post\s*$")).all()
                best, best_y, best_x = None, -1, -1
                for c in cands:
                    try:
                        if not (c.is_visible() and c.is_enabled()):
                            continue
                        bb = c.bounding_box()
                        y, x = (bb["y"], bb["x"]) if bb else (0, 0)
                        if (y, x) >= (best_y, best_x):
                            best, best_y, best_x = c, y, x
                    except Exception:  # noqa: BLE001
                        pass
                if best:
                    best.click()
                    posted = True
            except Exception:  # noqa: BLE001
                pass
            if not posted:
                try:
                    (dialog or page).keyboard.press("Control+Enter")
                except Exception:  # noqa: BLE001
                    page.keyboard.press("Control+Enter")
            page.wait_for_timeout(5000)
            try:
                still_open = False
                if dialog:
                    still_open = dialog.is_visible()
                else:
                    still_open = page.locator('div[role="textbox"]:has-text("%s")' % caption[:20]).count() > 0
                if still_open:
                    _debug_shot(ctx, account["id"], job_id, "not-posted")
                    raise RuntimeError(
                        "tombol Post diklik tapi composer masih kebuka, kemungkinan gagal kepost "
                        "(draft tersimpan / kena limit). Screenshot debug tersimpan di storage/%s/shots/." % account["id"])
            except RuntimeError:
                raise
            except Exception:  # noqa: BLE001
                pass
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
