PLATFORM_DOMAINS = {
    "threads": ["threads.net", ".threads.net", ".threads.com"],
    "instagram": ["instagram.com", ".instagram.com"],
    "facebook": ["facebook.com", ".facebook.com"],
    "x": ["x.com", ".x.com", "twitter.com", ".twitter.com"],
}

HOME_URLS = {
    "threads": "https://www.threads.net/",
    "instagram": "https://www.instagram.com/",
    "facebook": "https://www.facebook.com/",
    "x": "https://x.com/home",
}

LOGGED_IN_MARKERS = {
    "threads": ["threads", "login"],
    "instagram": ["instagram", "login"],
    "facebook": ["facebook", "login"],
    "x": ["x.com", "twitter"],
}

def _same_site(val):
    if not val:
        return "Lax"
    v = str(val).lower()
    if v in ("no_restriction", "none"):
        return "None"
    if v in ("lax", "strict"):
        return v.capitalize()
    return "Lax"

def parse_cookie_input(raw):
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("cookies kosong, paste dulu hasil export dari ekstensi")
    if raw.startswith("["):
        import json as js
        try:
            items = js.loads(raw)
        except Exception:
            raise ValueError("JSON tidak valid, pastikan copy full dari ekstensi tanpa kepotong")
        if not isinstance(items, list) or not items:
            raise ValueError("JSON valid tapi isinya kosong, export ulang dari tab yang sudah login")
        return _from_chrome_json(items)
    lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
    if lines and "\t" in lines[0]:
        return _from_netscape(lines)
    pairs = []
    for part in raw.replace("\n", ";").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and v:
                pairs.append((k, v))
    if not pairs:
        raise ValueError("format tidak dikenali, pakai JSON (disarankan) atau Netscape cookies.txt dari ekstensi")
    return [{"name": k, "value": v, "domain": "", "path": "/", "expires": -1,
             "httpOnly": False, "secure": True, "sameSite": "Lax"} for k, v in pairs]

def _chrome_exp(c):
    exp = c.get("expirationDate")
    if exp is None:
        return -1
    try:
        return float(exp)
    except (TypeError, ValueError):
        return -1

def _from_chrome_json(items):
    out = []
    for c in items:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        out.append({
            "name": c["name"], "value": c.get("value", ""),
            "domain": c.get("domain", ""), "path": c.get("path", "/") or "/",
            "expires": _chrome_exp(c),
            "httpOnly": bool(c.get("httpOnly", False)),
            "secure": bool(c.get("secure", True)),
            "sameSite": _same_site(c.get("sameSite")),
        })
    if not out:
        raise ValueError("tidak ada cookie valid di JSON tersebut")
    return out

def _from_netscape(lines):
    out = []
    for l in lines:
        parts = l.split("\t")
        if len(parts) < 7:
            continue
        domain, _, path, secure, exp, name, value = parts[:7]
        try:
            expf = float(exp)
        except ValueError:
            expf = -1
        out.append({"name": name, "value": value, "domain": domain, "path": path or "/",
                    "expires": expf, "httpOnly": False,
                    "secure": secure.upper() == "TRUE", "sameSite": "Lax"})
    if not out:
        raise ValueError("tidak ada baris cookie valid di file Netscape tersebut")
    return out

def check_relevant_domains(cookies, platform):
    wants = PLATFORM_DOMAINS.get(platform, [])
    got = {c.get("domain", "") for c in cookies if c.get("domain")}
    hit = any(any(w in g or g in w for w in wants) for g in got)
    return hit, sorted(got)[:8]

def verify_cookies(platform, cookies, proxy=""):
    from playwright.sync_api import sync_playwright
    from core.poster.base import launch_browser
    relevant, got = check_relevant_domains(cookies, platform)
    if not relevant:
        return False, ("cookie ini kayaknya bukan dari %s (domain ketemu: %s). "
                       "Buka %s di tab yang sudah login, baru export." % (
                           platform, ", ".join(got) if got else "-", HOME_URLS.get(platform, "")))
    try:
        with sync_playwright() as p:
            proxy_kw = {"server": proxy} if proxy else None
            browser = launch_browser(p, proxy_kw)
            try:
                ctx = browser.new_context()
                ctx.add_cookies(cookies)
                page = ctx.new_page()
                page.goto(HOME_URLS[platform], timeout=45000)
                page.wait_for_timeout(5000)
                url = page.url.lower()
                if "login" in url or "signin" in url or "auth" in url:
                    return False, "cookies kedaluwarsa atau tidak lengkap, masih dilempar ke halaman login. Login ulang di browser lalu export lagi."
                try:
                    title = page.title()
                except Exception:  # noqa: BLE001
                    title = ""
                return True, "login valid (%s)" % (title[:60] if title else url[:60])
            finally:
                browser.close()
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001
        return False, "gagal buka %s: %s" % (platform, str(e)[:200])
