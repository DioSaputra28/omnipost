from playwright.sync_api import sync_playwright
from core.poster.base import launch_context, save_state_and_shot
import logging as _logging
log = _logging.getLogger("omnipost")

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
            try:
                loc = page.get_by_text("New thread", exact=True).first
                if loc.count() and loc.is_visible():
                    loc.click()
                    opened = True
            except Exception:  # noqa: BLE001
                pass
            if not opened:
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
                for txt in ["What's new?", "What’s new?"]:
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
                box.click()
                page.keyboard.press("ControlOrMeta+a")
                page.keyboard.press("Backspace")
                page.wait_for_timeout(400)
            except Exception:  # noqa: BLE001
                pass
            import re as _re
            m = _re.search(r"https?://\S+", caption)
            link = m.group(0).rstrip(".,!?)") if m else ""
            text_only = _re.sub(r"https?://\S+", "", caption).strip()
            text_only = _re.sub(r"\s{2,}", " ", text_only)
            if not text_only:
                text_only = "Hari ini nemu barang bagus, cek komen buat linknya"
            try:
                box.click()
                for chunk in [text_only[i:i + 40] for i in range(0, len(text_only), 40)]:
                    page.keyboard.type(chunk, delay=15)
                    page.wait_for_timeout(120)
                page.wait_for_timeout(1200)
            except Exception:  # noqa: BLE001
                try:
                    box.fill(text_only)
                    page.wait_for_timeout(1200)
                except Exception:  # noqa: BLE001
                    pass
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
            scope_prev = dialog if dialog else page
            try:
                x_btn = None
                for b in scope_prev.locator('button, div[role="button"]').all():
                    try:
                        if not b.is_visible():
                            continue
                        bbx = b.bounding_box()
                        if not bbx:
                            continue
                        w, h = bbx["width"], bbx["height"]
                        if 18 <= w <= 34 and 18 <= h <= 34:
                            try:
                                txt = (b.inner_text() or "").strip()
                            except Exception:  # noqa: BLE001
                                txt = ""
                            if txt:
                                continue
                            try:
                                svg = b.locator("svg").count()
                            except Exception:  # noqa: BLE001
                                svg = 0
                            x_btn = (b, bbx, svg)
                            break
                    except Exception:  # noqa: BLE001
                        pass
                if x_btn:
                    try:
                        x_btn[0].click()
                        page.wait_for_timeout(800)
                    except Exception:  # noqa: BLE001
                        page.mouse.click(x_btn[1]["x"] + x_btn[1]["width"] / 2,
                                          x_btn[1]["y"] + x_btn[1]["height"] / 2)
                        page.wait_for_timeout(800)
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(1000)
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
            best = None
            for _ in range(6):
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
                        break
                except Exception:  # noqa: BLE001
                    pass
                page.wait_for_timeout(2000)
            if best:
                try:
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
                for sel in ['text="Save to drafts?"', 'button:has-text("Don\'t save")']:
                    try:
                        if page.locator(sel).count():
                            still_open = True
                            for ds in ['button:has-text("Don\'t save")']:
                                try:
                                    b = page.locator(ds).first
                                    if b.count() and b.is_visible():
                                        b.click()
                                        page.wait_for_timeout(1500)
                                except Exception:  # noqa: BLE001
                                    pass
                            break
                    except Exception:  # noqa: BLE001
                        pass
                if not still_open:
                    if dialog:
                        try:
                            still_open = dialog.is_visible()
                        except Exception:  # noqa: BLE001
                            still_open = False
                    else:
                        still_open = page.locator('div[role="textbox"]:has-text("%s")' % text_only[:20]).count() > 0
                if still_open:
                    _debug_shot(ctx, account["id"], job_id, "not-posted")
                    raise RuntimeError(
                        "tombol Post diklik tapi composer masih kebuka, kemungkinan gagal kepost "
                        "(draft tersimpan / kena limit). Screenshot debug tersimpan di storage/%s/shots/." % account["id"])
            except RuntimeError:
                raise
            except Exception:  # noqa: BLE001
                pass
            if link:
                try:
                    page.wait_for_timeout(4000)
                    username = (account.get("username") or "").strip().lstrip("@")
                    if not username:
                        try:
                            for a in page.locator('a[href^="/@"]').all()[:20]:
                                try:
                                    href = a.get_attribute("href") or ""
                                    if href.startswith("/@") and len(href) > 2:
                                        username = href[2:].split("/")[0]
                                        break
                                except Exception:  # noqa: BLE001
                                    pass
                        except Exception:  # noqa: BLE001
                            pass
                    if username:
                        page.goto("https://www.threads.com/@" + username, timeout=60000)
                        page.wait_for_timeout(5000)
                    hint = text_only[:24]
                    opened = page.evaluate("""(hint) => {
                        let node = null;
                        for (const e of document.querySelectorAll('div,span')) {
                            const t = (e.innerText || '').trim();
                            if (t.startsWith(hint) && t.length < hint.length + 120) { node = e; break; }
                        }
                        if (!node) return 'no-post';
                        let box = node;
                        for (let i = 0; i < 10; i++) {
                            if (!box.parentElement) break;
                            box = box.parentElement;
                            if (box.querySelectorAll('[role="button"]').length >= 3) break;
                        }
                        for (const bt of box.querySelectorAll('[role="button"], button')) {
                            const pEl = bt.querySelector('svg path');
                            const d = pEl ? (pEl.getAttribute('d') || '') : '';
                            if (d && d.indexOf('M12 3a9 9 0 0 0 0 18c1.414') === 0) {
                                bt.click();
                                return 'opened';
                            }
                        }
                        return 'no-reply-btn';
                    }""", hint)
                    log.info("reply open: %s", opened)
                    if opened == "opened":
                        page.wait_for_timeout(3000)
                        rbox = None
                        for sel in ['[contenteditable="true"]', 'div[role="textbox"]']:
                            try:
                                loc = page.locator(sel).first
                                loc.wait_for(state="visible", timeout=8000)
                                rbox = loc
                                break
                            except Exception:  # noqa: BLE001
                                pass
                        if rbox:
                            rbox.click()
                            page.wait_for_timeout(400)
                            for chunk in [link[i:i + 40] for i in range(0, len(link), 40)]:
                                page.keyboard.type(chunk, delay=15)
                                page.wait_for_timeout(100)
                            page.wait_for_timeout(3000)
                            sent = False
                            for _ in range(6):
                                try:
                                    res = page.evaluate("""() => {
                                        let best = null, bestX = -1;
                                        document.querySelectorAll('[role="button"], button').forEach(bt => {
                                            const r = bt.getBoundingClientRect();
                                            if (r.width === 0 || r.width > 60 || r.height > 60) return;
                                            if (r.y < 150) return;
                                            const bg = getComputedStyle(bt).backgroundColor;
                                            const pEl = bt.querySelector('svg path');
                                            const d = pEl ? (pEl.getAttribute('d') || '') : '';
                                            const isSend = bg === 'rgb(0, 0, 0)' && d && d.indexOf('M1 6h10') === 0;
                                            if (isSend && r.x > bestX) { best = bt; bestX = r.x; }
                                        });
                                        if (!best) return 'no-send';
                                        best.click();
                                        return 'sent';
                                    }""")
                                except Exception:  # noqa: BLE001
                                    res = "err"
                                if res == "sent":
                                    sent = True
                                    break
                                page.wait_for_timeout(2000)
                            page.wait_for_timeout(4000)
                            log.info("reply link: %s", "OK" if sent else "GAGAL")
                except Exception as e:  # noqa: BLE001
                    log.info("reply link skip: %s", str(e)[:150])
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
