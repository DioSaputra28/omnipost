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

def post(account, caption, job_id, include_link=True):
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
            cdp = ctx.new_cdp_session(page)

            def _ev(expr):
                try:
                    r = cdp.send("Runtime.evaluate", {
                        "expression": expr, "returnByValue": True, "awaitPromise": True,
                    })
                    return r.get("result", {}).get("value")
                except Exception:  # noqa: BLE001
                    return None

            def _click(x, y):
                cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
                cdp.send("Input.dispatchMouseEvent", {
                    "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
                cdp.send("Input.dispatchMouseEvent", {
                    "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})

            def _focus_editor():
                return _ev("""(() => {
                    const els = [...document.querySelectorAll('[contenteditable="true"]')];
                    if (!els.length) return 0;
                    els[els.length - 1].focus();
                    return els.length;
                })()""")

            def _insert(text):
                _focus_editor()
                page.wait_for_timeout(400)
                cdp.send("Input.insertText", {"text": text})
                page.wait_for_timeout(1200)

            def _card_box():
                return _ev("""(() => {
                    for (const bt of document.querySelectorAll('button, [role="button"]')) {
                        const r = bt.getBoundingClientRect();
                        if (r.width < 20 || r.width > 32 || r.height < 20 || r.height > 32) continue;
                        const pEl = bt.querySelector('svg path');
                        const d = pEl ? (pEl.getAttribute('d') || '') : '';
                        if (d.indexOf('M17.44 4.44') !== 0) continue;
                        let p = bt, depth = 0, hasLink = false;
                        while (p && depth < 8) {
                            const t = p.innerText || '';
                            if (t.includes('shop.ee') || t.includes('shopee')) { hasLink = true; break; }
                            p = p.parentElement; depth++;
                        }
                        if (!hasLink) continue;
                        return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2)};
                    }
                    return null;
                })()""")

            def _post_box():
                return _ev("""(() => {
                    let hit = null;
                    for (const bt of document.querySelectorAll('button, [role="button"]')) {
                        if ((bt.textContent || '').trim() !== 'Post') continue;
                        const r = bt.getBoundingClientRect();
                        if (r.width === 0 || r.height === 0 || r.y < 200) continue;
                        hit = {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
                               disabled: bt.disabled === true || bt.getAttribute('aria-disabled') === 'true'};
                    }
                    return hit;
                })()""")

            import re as _re
            m = _re.search(r"https?://\S+", caption)
            link = m.group(0).rstrip(".,!?)") if m else ""
            if not include_link:
                link = ""
            text_only = _re.sub(r"https?://\S+", "", caption).strip()
            text_only = _re.sub(r"\s{2,}", " ", text_only)
            if not text_only:
                text_only = "Hari ini nemu barang bagus, cek komen buat linknya"

            try:
                if page.locator('text="Who can reply and quote"').count():
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(800)
            except Exception:  # noqa: BLE001
                pass

            def _editors():
                raw = _ev("""(() => {
                    return JSON.stringify([...document.querySelectorAll('[contenteditable="true"]')].map(e => {
                        const r = e.getBoundingClientRect();
                        return {x: Math.round(r.x + r.width / 2),
                                y: Math.round(r.y + Math.min(r.height / 2, 12)),
                                txt: (e.innerText || '').slice(0, 30)};
                    }).filter(o => o.x > 0));
                })()""")
                try:
                    import json as _json
                    return _json.loads(raw) if raw else []
                except Exception:  # noqa: BLE001
                    return []

            def _click_editor(idx):
                eds = _editors()
                if not eds:
                    return False
                e = eds[idx]
                _click(e["x"], e["y"])
                page.wait_for_timeout(400)
                return True

            def _add_thread_box():
                return _ev("""(() => {
                    let best = null;
                    for (const el of document.querySelectorAll('div,span,button,[role="button"]')) {
                        if ((el.textContent || '').trim() !== 'Add to thread') continue;
                        const r = el.getBoundingClientRect();
                        if (r.width < 40 || r.width > 200 || r.height > 40 || r.height === 0) continue;
                        if (!best || r.y > best.y) best = {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2)};
                    }
                    return best;
                })()""")

            _focus_editor()
            page.wait_for_timeout(400)
            cdp.send("Input.insertText", {"text": text_only})
            page.wait_for_timeout(1200)

            mode = "inline"
            if link:
                at = _add_thread_box()
                if at:
                    _click(at["x"], at["y"])
                    page.wait_for_timeout(2500)
                if len(_editors()) >= 2:
                    mode = "thread"
                    _click_editor(-1)
                    cdp.send("Input.insertText", {"text": link})
                else:
                    mode = "inline"
                    cdp.send("Input.insertText", {"text": " " + link})
                page.wait_for_timeout(1500)
                log.info("mode link: %s", mode)

            card_ok = True
            if link:
                card = None
                for _ in range(12):
                    card = _card_box()
                    if card:
                        break
                    page.wait_for_timeout(1000)
                log.info("preview card: %s", "muncul" if card else "tidak muncul")
                if card:
                    for attempt in range(2):
                        _click(card["x"], card["y"])
                        page.wait_for_timeout(1500)
                        card = _card_box()
                        log.info("hapus kartu #%d: %s", attempt + 1, "OK" if not card else "masih ada")
                        if not card:
                            break
                    card_ok = not card

            post_btn = _post_box()
            link_in_post = bool(link) and card_ok
            if link and (not card_ok or (post_btn and post_btn.get("disabled"))):
                log.info("fallback: teks saja + link di reply")
                _click_editor(-1)
                page.keyboard.press("ControlOrMeta+a")
                page.keyboard.press("Backspace")
                page.wait_for_timeout(800)
                if mode == "inline":
                    cdp.send("Input.insertText", {"text": text_only})
                    page.wait_for_timeout(1200)
                link_in_post = False

            posted = False
            for _ in range(6):
                post_btn = _post_box()
                if post_btn and not post_btn.get("disabled"):
                    _click(post_btn["x"], post_btn["y"])
                    posted = True
                    break
                page.wait_for_timeout(2000)
            if not posted:
                try:
                    page.keyboard.press("Control+Enter")
                except Exception:  # noqa: BLE001
                    pass
            page.wait_for_timeout(12000)
            try:
                still_open = False
                for sel in ['text="Save to drafts?"', 'button:has-text("Don\'t save")']:
                    try:
                        if page.locator(sel).count():
                            still_open = True
                            b = page.locator('button:has-text("Don\'t save")').first
                            if b.count() and b.is_visible():
                                b.click()
                                page.wait_for_timeout(1500)
                            break
                    except Exception:  # noqa: BLE001
                        pass
                if not still_open:
                    still_open = bool(_ev("""(() => {
                        const els = [...document.querySelectorAll('[contenteditable="true"]')];
                        return els.length > 0 && els[els.length - 1].getBoundingClientRect().width > 0
                            && document.body.innerText.indexOf('New thread') >= 0;
                    })()"""))
                if still_open:
                    _debug_shot(ctx, account["id"], job_id, "not-posted")
                    raise RuntimeError(
                        "tombol Post diklik tapi composer masih kebuka, kemungkinan gagal kepost "
                        "(draft tersimpan / kena limit). Screenshot debug tersimpan di storage/%s/shots/." % account["id"])
            except RuntimeError:
                raise
            except Exception:  # noqa: BLE001
                pass

            if link and not link_in_post:
                try:
                    username = (account.get("username") or "").strip().lstrip("@")
                    if username:
                        page.goto("https://www.threads.com/@" + username, timeout=60000)
                        page.wait_for_timeout(5000)
                    import json as _json
                    hint_js = _json.dumps(text_only[:24])
                    nav = _ev("(() => { const hint = " + hint_js + ";"
                              " for (const e of document.querySelectorAll('div,span')) {"
                              " const t = (e.innerText || '').trim();"
                              " if (t.startsWith(hint) && t.length < hint.length + 120) { e.click(); return 'clicked'; } }"
                              " return 'no-post'; })()")
                    log.info("reply nav: %s", nav)
                    if nav == "clicked":
                        page.wait_for_timeout(5000)
                        expanded = False
                        for _ in range(3):
                            try:
                                loc = page.locator('[aria-label="Expand composer"]').first
                                if loc.count() and loc.is_visible():
                                    loc.click()
                                    expanded = True
                                    break
                            except Exception:  # noqa: BLE001
                                pass
                            page.wait_for_timeout(2000)
                        log.info("reply expand: %s", expanded)
                        if expanded:
                            page.wait_for_timeout(2500)
                            _insert(link)
                            posted_reply = False
                            for _ in range(6):
                                box = _post_box()
                                if box and not box.get("disabled"):
                                    _click(box["x"], box["y"])
                                    posted_reply = True
                                    break
                                page.wait_for_timeout(2000)
                            page.wait_for_timeout(5000)
                            log.info("reply link: %s", "OK" if posted_reply else "GAGAL")
                except Exception as e:  # noqa: BLE001
                    log.info("reply link skip: %s", str(e)[:150])
            shot = save_state_and_shot(ctx, state_path, account["id"], job_id)
            return shot
        finally:
            browser.close()

def _cdp(cdp, expr):
    try:
        r = cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return r.get("result", {}).get("value")
    except Exception:  # noqa: BLE001
        return None

def _cdp_click(cdp, x, y):
    cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})

_CARD_JS = """(() => {
    for (const bt of document.querySelectorAll('button, [role="button"]')) {
        const r = bt.getBoundingClientRect();
        if (r.width < 20 || r.width > 32 || r.height < 20 || r.height > 32) continue;
        const pEl = bt.querySelector('svg path');
        const d = pEl ? (pEl.getAttribute('d') || '') : '';
        if (d.indexOf('M17.44 4.44') !== 0) continue;
        let p = bt, depth = 0, hasLink = false;
        while (p && depth < 8) {
            const t = p.innerText || '';
            if (t.includes('shop.ee') || t.includes('shopee')) { hasLink = true; break; }
            p = p.parentElement; depth++;
        }
        if (!hasLink) continue;
        return {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2)};
    }
    return null;
})()"""

def add_link_reply(account, post_url, link, job_id=None):
    with sync_playwright() as p:
        browser, ctx, state_path = launch_context(p, account)
        try:
            page = ctx.new_page()
            cdp = ctx.new_cdp_session(page)
            page.goto(post_url, timeout=60000)
            page.wait_for_timeout(5000)

            opened = _cdp(cdp, """(() => {
                for (const el of document.querySelectorAll('div,span')) {
                    const t = (el.innerText || '').trim();
                    if (t.startsWith('Reply to ') && t.length < 60) { el.click(); return 'ok'; }
                }
                for (const e of document.querySelectorAll('[contenteditable="true"]')) { e.focus(); return 'editor'; }
                return 'none';
            })()""")
            log.info("autolink reply buka: %s", opened)
            if opened == "none":
                return False
            page.wait_for_timeout(1500)

            expanded = _cdp(cdp, """(() => {
                for (const bt of document.querySelectorAll('[role="button"], button')) {
                    if (bt.getAttribute('aria-label') === 'Expand composer') { bt.click(); return 'ok'; }
                }
                return 'none';
            })()""")
            log.info("autolink reply expand: %s", expanded)
            page.wait_for_timeout(3000)

            _cdp(cdp, """(() => { const e=[...document.querySelectorAll('[contenteditable="true"]')]; if (e.length) e[e.length-1].focus(); })()""")
            page.wait_for_timeout(400)
            for chunk in [link[i:i + 40] for i in range(0, len(link), 40)]:
                cdp.send("Input.insertText", {"text": chunk})
                page.wait_for_timeout(120)

            card = None
            for _ in range(15):
                card = _cdp(cdp, _CARD_JS)
                if card:
                    break
                page.wait_for_timeout(1000)
            log.info("autolink kartu: %s", "muncul" if card else "tidak muncul")
            if card:
                for attempt in range(2):
                    _cdp_click(cdp, card["x"], card["y"])
                    page.wait_for_timeout(1500)
                    card = _cdp(cdp, _CARD_JS)
                    log.info("autolink hapus kartu #%d: %s", attempt + 1, "OK" if not card else "masih ada")
                    if not card:
                        break

            posted = False
            for _ in range(6):
                box = _cdp(cdp, """(() => {
                    let hit = null;
                    for (const bt of document.querySelectorAll('button, [role="button"]')) {
                        if ((bt.textContent || '').trim() !== 'Post') continue;
                        const r = bt.getBoundingClientRect();
                        if (r.width === 0 || r.height === 0) continue;
                        hit = {x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
                               disabled: bt.disabled === true};
                    }
                    return hit;
                })()""")
                if box and not box.get("disabled"):
                    _cdp_click(cdp, box["x"], box["y"])
                    posted = True
                    break
                page.wait_for_timeout(2000)
            page.wait_for_timeout(8000)
            log.info("autolink reply: %s", "OK" if posted else "GAGAL")
            return posted
        finally:
            browser.close()

def post_to_platform(account, caption, job_id, include_link=True):
    plat = (account.get("platform") or "").lower()
    if plat == "threads":
        return post(account, caption, job_id, include_link=include_link)
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
