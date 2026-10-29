import os
from playwright.sync_api import sync_playwright
from core.poster.base import launch_browser, account_dir

LINK = "https://s.shopee.co.id/9KZr6oKxU7"
STORY = "TEST-CDP-2 aku nemu camilan enak banget hari ini, beneran worth it."

def ev(cdp, expr):
    r = cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    return r.get("result", {}).get("value")

def click_at(cdp, x, y):
    cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})

CARD_JS = """(() => {
    const btns = [...document.querySelectorAll('button, [role="button"]')];
    for (const bt of btns) {
        const r = bt.getBoundingClientRect();
        if (r.width < 20 || r.width > 32 || r.height < 20 || r.height > 32) continue;
        const pEl = bt.querySelector('svg path');
        const d = pEl ? (pEl.getAttribute('d') || '') : '';
        if (d.indexOf('M17.44 4.44') !== 0) continue;
        let p = bt, depth = 0, hasLink = false;
        while (p && depth < 8) {
            if ((p.innerText || '').includes('shop.ee') || (p.innerText || '').includes('s.shopee')) { hasLink = true; break; }
            p = p.parentElement; depth++;
        }
        if (!hasLink) continue;
        return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)};
    }
    return null;
})()"""

POST_JS = """(() => {
    const btns = [...document.querySelectorAll('button, [role="button"]')];
    for (const bt of btns) {
        if ((bt.textContent || '').trim() !== 'Post') continue;
        const r = bt.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        if (r.y < 200) continue;
        return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2),
                disabled: bt.disabled || bt.getAttribute('aria-disabled') === 'true'};
    }
    return null;
})()"""

with sync_playwright() as p:
    b = launch_browser(p)
    ctx = b.new_context(storage_state=os.path.join(account_dir(3), "storage_state.json"))
    pg = ctx.new_page()
    cdp = ctx.new_cdp_session(pg)
    pg.goto("https://www.threads.com/", timeout=60000)
    pg.wait_for_timeout(6000)

    pg.get_by_text("New thread", exact=True).first.click()
    pg.wait_for_timeout(3000)
    ev(cdp, """(() => { const e=[...document.querySelectorAll('[contenteditable="true"]')]; if(!e.length) return 0; e[e.length-1].focus(); return e.length; })()""")
    pg.wait_for_timeout(400)
    cdp.send("Input.insertText", {"text": STORY + " " + LINK})
    pg.wait_for_timeout(1500)

    card = None
    for i in range(15):
        card = ev(cdp, CARD_JS)
        print(f"poll kartu {i}:", card)
        if card:
            break
        pg.wait_for_timeout(1000)

    if card:
        for attempt in range(2):
            print(f"klik X #{attempt+1} di", card)
            click_at(cdp, card["x"], card["y"])
            pg.wait_for_timeout(2000)
            still = ev(cdp, CARD_JS)
            print("sisa kartu:", still)
            if not still:
                break
            card = still
        pg.screenshot(path="/tmp/cdp_2_removed.png")

    post = ev(cdp, POST_JS)
    print("tombol post:", post)
    if post and not post["disabled"]:
        click_at(cdp, post["x"], post["y"])
        print("diklik")
    pg.wait_for_timeout(14000)
    pg.screenshot(path="/tmp/cdp_3_posted.png")
    ctx.close()
    b.close()
