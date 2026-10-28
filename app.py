import functools
import json
import os
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from core.db import get_conn, init_db, get_setting, set_setting
from core.ai import generate_story, _cfg
from core.scheduler import start_scheduler, run_job_for_account

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("uid"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/login", methods=["GET", "POST"])
def login():
    conn = get_conn()
    has_user = conn.execute("SELECT COUNT(*) c FROM user").fetchone()["c"]
    conn.close()
    if request.method == "POST":
        u, pw = request.form["username"], request.form["password"]
        conn = get_conn()
        if not has_user:
            conn.execute("INSERT INTO user (username, password_hash) VALUES (?,?)",
                         (u, generate_password_hash(pw)))
            conn.commit()
            uid = conn.execute("SELECT id FROM user WHERE username=?", (u,)).fetchone()["id"]
            conn.close()
            session["uid"] = uid
            return redirect(url_for("index"))
        row = conn.execute("SELECT * FROM user WHERE username=?", (u,)).fetchone()
        conn.close()
        if row and check_password_hash(row["password_hash"], pw):
            session["uid"] = row["id"]
            return redirect(url_for("index"))
        flash("login gagal")
    return render_template("login.html", first_run=not has_user)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    conn = get_conn()
    stats = {
        "akun": conn.execute("SELECT COUNT(*) c FROM social_accounts").fetchone()["c"],
        "akun_aktif": conn.execute("SELECT COUNT(*) c FROM social_accounts WHERE status='ok'").fetchone()["c"],
        "produk": conn.execute("SELECT COUNT(*) c FROM products WHERE aktif=1").fetchone()["c"],
        "posted": conn.execute("SELECT COUNT(*) c FROM jobs WHERE status='posted'").fetchone()["c"],
        "failed": conn.execute("SELECT COUNT(*) c FROM jobs WHERE status='failed'").fetchone()["c"],
    }
    total = stats["posted"] + stats["failed"]
    rate = round(stats["posted"] / total * 100, 1) if total else 0
    queued = conn.execute("SELECT COUNT(*) c FROM jobs WHERE status='queued'").fetchone()["c"]
    jobs = conn.execute(
        "SELECT j.*, s.label, s.platform, p.nama FROM jobs j "
        "JOIN social_accounts s ON s.id=j.account_id "
        "JOIN products p ON p.id=j.product_id ORDER BY j.id DESC LIMIT 20").fetchall()
    accs = conn.execute("SELECT * FROM social_accounts").fetchall()
    prods = conn.execute("SELECT * FROM products WHERE aktif=1").fetchall()
    today = datetime.now().strftime("%A, %d %B %Y")
    today_jobs = conn.execute(
        "SELECT j.*, s.label, s.platform, p.nama, p.link_shopee FROM jobs j "
        "JOIN social_accounts s ON s.id=j.account_id "
        "JOIN products p ON p.id=j.product_id "
        "WHERE date(j.scheduled_at)=date('now','localtime') ORDER BY j.id DESC LIMIT 10").fetchall()
    perf = conn.execute(
        "SELECT s.label, s.platform, "
        "SUM(CASE WHEN j.status='posted' THEN 1 ELSE 0 END) posted, "
        "SUM(CASE WHEN j.status='failed' THEN 1 ELSE 0 END) failed "
        "FROM social_accounts s LEFT JOIN jobs j ON j.account_id=s.id "
        "GROUP BY s.id").fetchall()
    conn.close()
    return render_template("index.html", stats=stats, jobs=jobs, rate=rate,
                           queued=queued, accs=accs, prods=prods,
                           today=today, today_jobs=today_jobs, perf=perf, nav="dash")

@app.route("/akun", methods=["GET"])
@login_required
def akun():
    from core.login_session import pending_login_token
    conn = get_conn()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(social_accounts)").fetchall()]
    if "login_token" not in cols:
        conn.execute("ALTER TABLE social_accounts ADD COLUMN login_token TEXT DEFAULT ''")
        conn.commit()
    rows = conn.execute("SELECT * FROM social_accounts ORDER BY id DESC").fetchall()
    pending = pending_login_token()
    conn.close()
    return render_template("akun.html", rows=rows, nav="akun", pending_token=pending)

@app.route("/akun/hubungkan", methods=["POST"])
@login_required
def akun_hubungkan():
    from core.login_session import start_login_session
    from core.cookie_import import parse_cookie_input, verify_cookies
    platform = request.form.get("platform", "threads")
    label = request.form.get("label", f"{platform}-1").strip() or f"{platform}-1"
    proxy = request.form.get("proxy", "").strip()
    cookie_raw = ""
    if "cookie_file" in request.files and request.files["cookie_file"].filename:
        cookie_raw = request.files["cookie_file"].read().decode("utf-8", errors="ignore")
    else:
        cookie_raw = request.form.get("cookies", "")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO social_accounts (platform,label,proxy,status) VALUES (?,?,?,'checking')",
        (platform, label, proxy))
    aid = cur.lastrowid
    conn.commit()
    conn.close()
    if cookie_raw.strip():
        try:
            cookies = parse_cookie_input(cookie_raw)
        except ValueError as e:
            conn = get_conn()
            conn.execute("DELETE FROM social_accounts WHERE id=?", (aid,))
            conn.commit()
            conn.close()
            flash(f"cookies tidak bisa dibaca: {e}")
            return redirect(url_for("akun"))
        ok, msg = verify_cookies(platform, cookies, proxy)
        if not ok:
            conn = get_conn()
            conn.execute("DELETE FROM social_accounts WHERE id=?", (aid,))
            conn.commit()
            conn.close()
            flash(f"cookies tidak works: {msg}")
            return redirect(url_for("akun"))
        from core.poster.base import account_dir
        import json as js
        state = {"cookies": cookies, "origins": []}
        with open(os.path.join(account_dir(aid), "storage_state.json"), "w") as f:
            js.dump(state, f)
        conn = get_conn()
        conn.execute("UPDATE social_accounts SET status='ok' WHERE id=?", (aid,))
        conn.commit()
        conn.close()
        flash(f"akun {label} ditambahkan, cookies works. {msg}")
        return redirect(url_for("akun"))
    try:
        token = start_login_session(platform, label, proxy)
    except Exception as e:  # noqa: BLE001
        conn = get_conn()
        conn.execute("UPDATE social_accounts SET status='error' WHERE id=?", (aid,))
        conn.commit()
        conn.close()
        flash(f"gagal buka browser login: {e}")
        return redirect(url_for("akun"))
    conn = get_conn()
    conn.execute("UPDATE social_accounts SET login_token=? WHERE id=?", (token, aid))
    conn.commit()
    conn.close()
    return redirect(url_for("akun_login", aid=aid))

@app.route("/akun/<int:aid>/login")
@login_required
def akun_login(aid):
    conn = get_conn()
    acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (aid,)).fetchone()
    conn.close()
    if not acc:
        return redirect(url_for("akun"))
    urls = {"threads": "https://www.threads.net/login", "instagram": "https://www.instagram.com/accounts/login/",
            "facebook": "https://www.facebook.com/login/", "x": "https://x.com/login"}
    return render_template("akun_login.html", acc=acc, login_url=urls.get(acc["platform"], "#"), nav="akun")

@app.route("/akun/<int:aid>/simpan-sesi", methods=["POST"])
@login_required
def akun_simpan_sesi(aid):
    from core.login_session import finish_login_session
    conn = get_conn()
    acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (aid,)).fetchone()
    conn.close()
    if not acc or not acc["login_token"]:
        flash("tidak ada sesi login aktif untuk akun ini")
        return redirect(url_for("akun"))
    try:
        info = finish_login_session(acc["login_token"], aid)
        conn = get_conn()
        conn.execute("UPDATE social_accounts SET login_token='' WHERE id=?", (aid,))
        conn.commit()
        conn.close()
        flash(f"sesi tersimpan ({info.get('title','')[:40]}). Akun siap posting.")
    except Exception as e:  # noqa: BLE001
        flash(f"gagal simpan sesi: {e}")
    return redirect(url_for("akun"))

@app.route("/akun/<int:aid>/batal-login", methods=["POST"])
@login_required
def akun_batal_login(aid):
    from core.login_session import cancel_login_session
    conn = get_conn()
    acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (aid,)).fetchone()
    if acc and acc["login_token"]:
        cancel_login_session(acc["login_token"])
    if acc and acc["status"] == "waiting-login":
        conn.execute("DELETE FROM social_accounts WHERE id=?", (aid,))
    else:
        conn.execute("UPDATE social_accounts SET login_token='' WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    return redirect(url_for("akun"))

@app.route("/akun/<int:aid>/cookies", methods=["POST"])
@login_required
def akun_cookies(aid):
    raw = request.form.get("cookies", "")
    conn = get_conn()
    acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (aid,)).fetchone()
    conn.close()
    if not acc:
        return redirect(url_for("akun"))
    from core.poster.base import account_dir
    import json as js
    d = account_dir(aid)
    cookies = js.loads(raw) if raw.strip().startswith("[") else [{"name": "c", "value": raw}]
    state = {"cookies": cookies, "origins": []}
    with open(os.path.join(d, "storage_state.json"), "w") as f:
        js.dump(state, f)
    conn = get_conn()
    conn.execute("UPDATE social_accounts SET status='cookies-ok' WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    flash("cookies tersimpan")
    return redirect(url_for("akun"))

@app.route("/akun/<int:aid>/relogin")
@login_required
def akun_relogin(aid):
    from core.login_session import start_login_session
    conn = get_conn()
    acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (aid,)).fetchone()
    conn.close()
    if not acc:
        return redirect(url_for("akun"))
    try:
        token = start_login_session(acc["platform"], acc["label"], acc["proxy"] or "")
    except Exception as e:  # noqa: BLE001
        flash(f"gagal buka browser login: {e}")
        return redirect(url_for("akun"))
    conn = get_conn()
    conn.execute("UPDATE social_accounts SET login_token=?, status='waiting-login' WHERE id=?", (token, aid))
    conn.commit()
    conn.close()
    return redirect(url_for("akun_login", aid=aid))

@app.route("/akun/<int:aid>/toggle-pause")
@login_required
def akun_pause(aid):
    conn = get_conn()
    cur = conn.execute("SELECT status FROM social_accounts WHERE id=?", (aid,)).fetchone()
    if not cur:
        conn.close()
        return redirect(url_for("akun"))
    ns = "paused" if cur["status"] != "paused" else "ok"
    conn.execute("UPDATE social_accounts SET status=? WHERE id=?", (ns, aid))
    conn.commit()
    conn.close()
    return redirect(url_for("akun"))

@app.route("/akun/<int:aid>/hapus", methods=["POST"])
@login_required
def akun_hapus(aid):
    import shutil
    from core.poster.base import account_dir
    from core.login_session import cancel_login_session
    conn = get_conn()
    acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (aid,)).fetchone()
    if not acc:
        conn.close()
        flash("akun tidak ketemu")
        return redirect(url_for("akun"))
    if acc["login_token"]:
        cancel_login_session(acc["login_token"])
    label = acc["label"]
    conn.execute("DELETE FROM social_accounts WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    shutil.rmtree(account_dir(aid), ignore_errors=True)
    try:
        from core.login_session import SESSIONS
        for tok in [t for t, s in SESSIONS.items() if s.get("label") == label]:
            cancel_login_session(tok)
    except Exception:  # noqa: BLE001
        pass
    flash(f"akun {label} dihapus (persona, jobs, dan sesi ikut kehapus)")
    return redirect(url_for("akun"))

@app.route("/akun/<int:aid>")
@login_required
def akun_detail(aid):
    conn = get_conn()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(social_accounts)").fetchall()]
    if "user_agent" not in cols:
        conn.execute("ALTER TABLE social_accounts ADD COLUMN user_agent TEXT DEFAULT ''")
        conn.commit()
    acc = conn.execute("SELECT * FROM social_accounts WHERE id=?", (aid,)).fetchone()
    if not acc:
        conn.close()
        return redirect(url_for("akun"))
    persona = conn.execute("SELECT * FROM personas WHERE account_id=? LIMIT 1", (aid,)).fetchone()
    jobs = conn.execute(
        "SELECT j.*, p.nama FROM jobs j JOIN products p ON p.id=j.product_id "
        "WHERE j.account_id=? ORDER BY j.id DESC LIMIT 20", (aid,)).fetchall()
    posted = conn.execute("SELECT COUNT(*) c FROM jobs WHERE account_id=? AND status='posted'", (aid,)).fetchone()["c"]
    failed = conn.execute("SELECT COUNT(*) c FROM jobs WHERE account_id=? AND status='failed'", (aid,)).fetchone()["c"]
    conn.close()
    from core.user_agents import USER_AGENTS, ua_usage
    return render_template("akun_detail.html", acc=acc, persona=persona, jobs=jobs,
                           posted=posted, failed=failed, nav="akun",
                           user_agents=USER_AGENTS, ua_used=ua_usage(aid))

@app.route("/akun/<int:aid>/simpan", methods=["POST"])
@login_required
def akun_simpan(aid):
    conn = get_conn()
    conn.execute(
        "UPDATE social_accounts SET label=?, proxy=?, user_agent=?, posts_per_day=?, active_hour_start=?, active_hour_end=? WHERE id=?",
        (request.form.get("label", "").strip(),
         request.form.get("proxy", "").strip(),
         request.form.get("user_agent", "").strip(),
         int(request.form.get("posts_per_day", 3) or 3),
         int(request.form.get("hour_start", 7) or 7),
         int(request.form.get("hour_end", 21) or 21),
         aid))
    conn.commit()
    conn.close()
    flash("pengaturan akun tersimpan")
    return redirect(url_for("akun_detail", aid=aid))

@app.route("/akun/<int:aid>/persona", methods=["POST"])
@login_required
def akun_persona(aid):
    conn = get_conn()
    cur = conn.execute("SELECT id FROM personas WHERE account_id=? LIMIT 1", (aid,)).fetchone()
    if cur:
        conn.execute("UPDATE personas SET nama=?, gaya_bahasa=?, system_prompt=?, contoh_cerita=? WHERE id=?",
                     (request.form["nama"], request.form.get("gaya_bahasa", ""),
                      request.form["system_prompt"], request.form.get("contoh_cerita", ""), cur["id"]))
    else:
        conn.execute("INSERT INTO personas (account_id,nama,gaya_bahasa,system_prompt,contoh_cerita) VALUES (?,?,?,?,?)",
                     (aid, request.form["nama"], request.form.get("gaya_bahasa", ""),
                      request.form["system_prompt"], request.form.get("contoh_cerita", "")))
    conn.commit()
    conn.close()
    flash("persona tersimpan")
    return redirect(url_for("akun_detail", aid=aid))

@app.route("/persona", methods=["GET"])
@login_required
def persona():
    return redirect(url_for("akun"))

@app.route("/produk", methods=["GET", "POST"])
@login_required
def produk():
    conn = get_conn()
    if request.method == "POST":
        if "csv" in request.files and request.files["csv"].filename:
            import csv, io
            text = io.StringIO(request.files["csv"].read().decode("utf-8"))
            for r in csv.DictReader(text):
                conn.execute("INSERT INTO products (nama,link_shopee,deskripsi,kategori) VALUES (?,?,?,?)",
                             (r.get("nama", ""), r.get("link_shopee", ""), r.get("deskripsi", ""), r.get("kategori", "")))
            conn.commit()
        else:
            conn.execute("INSERT INTO products (nama,link_shopee,deskripsi,kategori) VALUES (?,?,?,?)",
                         (request.form["nama"], request.form["link_shopee"],
                          request.form.get("deskripsi", ""), request.form.get("kategori", "")))
            conn.commit()
    rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("produk.html", rows=rows, nav="produk")

@app.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    out = None
    picked_aid = picked_pid = None
    conn = get_conn()
    accs = conn.execute("SELECT * FROM social_accounts").fetchall()
    prods = conn.execute("SELECT * FROM products WHERE aktif=1").fetchall()
    conn.close()
    if request.method == "POST":
        aid, pid = int(request.form["account_id"]), int(request.form["product_id"])
        picked_aid, picked_pid = aid, pid
        conn = get_conn()
        per = conn.execute("SELECT * FROM personas WHERE account_id=? LIMIT 1", (aid,)).fetchone()
        prod = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        conn.close()
        if per and prod:
            out = generate_story(per["system_prompt"], per["gaya_bahasa"], per["contoh_cerita"],
                                 prod["nama"], prod["deskripsi"], prod["link_shopee"])
        else:
            flash("akun ini belum punya persona / produk tidak ketemu")
    return render_template("generate.html", accs=accs, prods=prods, out=out,
                           picked_aid=picked_aid, picked_pid=picked_pid, nav="gen")

@app.route("/post-now", methods=["POST"])
@login_required
def post_now():
    jid, err = run_job_for_account(int(request.form["account_id"]), int(request.form.get("product_id") or 0) or None)
    flash(f"job #{jid} gagal: {err}" if err else f"job #{jid} posted!")
    return redirect(url_for("index"))

@app.route("/setting-ai", methods=["GET", "POST"])
@login_required
def setting_ai():
    if request.method == "POST":
        set_setting("ai_base_url", request.form.get("ai_base_url", "").strip() or "https://api.openai.com/v1")
        set_setting("ai_api_key", request.form.get("ai_api_key", "").strip())
        set_setting("ai_model", request.form.get("ai_model", "").strip() or "gpt-4o-mini")
        if request.form.get("test") == "1":
            try:
                base_url, _, model = _cfg()
                generate_story("Kamu asisten.", "santai", "-", "Teh test", "produk dummy", "https://shopee.co.id/x")
                flash(f"koneksi OK ke {base_url} model {model}")
            except Exception as e:  # noqa: BLE001
                flash(f"test gagal: {e}")
        else:
            flash("setting AI tersimpan")
        return redirect(url_for("setting_ai"))
    cfg = {"ai_base_url": get_setting("ai_base_url"), "ai_api_key": get_setting("ai_api_key"), "ai_model": get_setting("ai_model")}
    masked = (cfg["ai_api_key"][:4] + "..." + cfg["ai_api_key"][-4:]) if len(cfg["ai_api_key"]) > 8 else ("..." if cfg["ai_api_key"] else "-")
    return render_template("setting_ai.html", cfg=cfg, masked=masked, nav="setting")

@app.route("/jadwal")
@login_required
def jadwal():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM social_accounts").fetchall()
    queued = conn.execute(
        "SELECT j.*, s.label, s.platform, p.nama, p.link_shopee FROM jobs j "
        "JOIN social_accounts s ON s.id=j.account_id "
        "JOIN products p ON p.id=j.product_id "
        "WHERE j.status='queued' ORDER BY j.id DESC LIMIT 30").fetchall()
    drafts = []
    posted_month = conn.execute("SELECT COUNT(*) c FROM jobs WHERE status='posted' AND scheduled_at IS NOT NULL").fetchone()["c"]
    quota = []
    for r in rows:
        today_n = conn.execute(
            "SELECT COUNT(*) c FROM jobs WHERE account_id=? AND status='posted' AND date(posted_at)=date('now','localtime')",
            (r["id"],)).fetchone()["c"]
        pct = min(100, round(today_n / max(r["posts_per_day"] or 1, 1) * 100))
        quota.append({"label": r["label"], "today": today_n, "posts_per_day": r["posts_per_day"], "pct": pct})
    conn.close()
    return render_template("jadwal.html", rows=rows, queued=queued, drafts=drafts,
                           posted_month=posted_month, quota=quota, nav="jadwal")

@app.route("/jadwal/<int:aid>", methods=["POST"])
@login_required
def jadwal_save(aid):
    conn = get_conn()
    conn.execute("UPDATE social_accounts SET posts_per_day=?, active_hour_start=?, active_hour_end=? WHERE id=?",
                 (int(request.form["posts_per_day"]), int(request.form["hour_start"]),
                  int(request.form["hour_end"]), aid))
    conn.commit()
    conn.close()
    return redirect(url_for("jadwal"))

if __name__ == "__main__":
    init_db()
    start_scheduler()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
