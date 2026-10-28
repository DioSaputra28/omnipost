# Omnipost — Autopost Affiliate Shopee

Web app personal-use (single user) untuk auto-posting produk affiliate Shopee ke **Threads, Instagram, Facebook, dan X/Twitter**. Tanpa API resmi Meta/X — memakai **browser automation (Playwright + Chromium)** yang meniru manusia. **AI (OpenAI-compatible)** membuat cerita soft-selling yang disisipi link Shopee, mengikuti persona tiap akun. **Scheduler** jalan otomatis dengan jeda acak + jitter, dedup produk 14 hari, proxy & user-agent per akun.

## Fitur

- **Login personal** — single user, kunjungan pertama = buat akun
- **Kelola akun sosmed** — 2 cara menambah akun:
  - **Import cookies** (disarankan): install ekstensi [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc), export JSON di tab yang sudah login, paste/upload ke form — sistem langsung **test otomatis** (parse format → cek domain → buka beranda headless). Gagal = pesan jelas kenapa, akun sampah auto-dihapus
  - **Login manual via browser**: server bukakan Chromium ke halaman login, login manual (captcha/2FA bebas), klik simpan sesi
- **Detail akun** — klik Detail di tiap kartu: persona, pengaturan (label, proxy, jadwal), user-agent, riwayat 20 job, hapus akun
- **Persona per akun** — nama, gaya bahasa, system prompt, contoh cerita (few-shot). 1 akun = 1 persona
- **Produk affiliate** — CRUD + import CSV (`nama,link_shopee,deskripsi,kategori`)
- **AI storytelling** — preview generate sebelum posting, protokol OpenAI-compatible (base URL + API key + model bisa diganti dari web UI di menu Setting AI)
- **Scheduler** — per akun: post/hari, jam aktif, cek tiap 5 menit + jitter 5–25 menit, dedup (akun+produk) 14 hari, antre 1-1 bergantian
- **Anti-spam** — proxy per akun + 102 pilihan user-agent (tanda mana yang sudah dipakai akun lain)
- **Bukti posting** — screenshot tiap job sukses/gagal di `storage/<id>/shots/`

## Requirement

| Kebutuhan | Versi teruji | Keterangan |
|---|---|---|
| Python | 3.14.3 (min 3.11) | `python3 --version` |
| Flask | 3.1.3 | web panel |
| Playwright (Python) | 1.63.0 | browser automation, `playwright>=1.44` |
| Chromium (via Playwright) | 145 (build 1208) | `python -m playwright install chromium` (~150MB). Ada fallback otomatis ke Chromium cache/sistem |
| APScheduler | 3.11.3 | scheduler interval |
| python-dotenv | 1.2.4 | baca `.env` |
| openai (Python SDK) | 3.24.0 | client OpenAI-compatible, `openai>=1.30` |
| SQLite | bawaan Python | database file `db.sqlite`, tanpa server tambahan |
| Browser login manual | butuh display | VNC/RDP kalau di VPS headless |
| Internet | wajib | Tailwind? **tidak** — semua CSS/font/ikon lokal (full offline kecuali AI + posting) |

> Catatan: `requirements.txt` memakai batas bawah (`>=`) supaya `pip install` selalu dapat versi kompatibel terbaru. Tabel di atas adalah versi yang teruji jalan.

## Instalasi

```bash
# 1. clone
git clone git@github.com:DioSaputra28/omnipost.git
cd omnipost

# 2. venv + dependencies (pakai uv, cepat; atau python -m venv + pip)
uv venv
uv pip install -r requirements.txt
# alternatif: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# 3. browser Chromium untuk Playwright
.venv/bin/python -m playwright install chromium

# 4. config
cp .env.example .env
# isi minimal: SECRET_KEY (random), OPENAI_API_KEY (sk-...), BROWSER_HEADLESS, PORT
```

Isi `.env`:

```
SECRET_KEY=ganti-dengan-random-string
BROWSER_HEADLESS=true        # false = browser nongol (buat login awal/debug)
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-isi-api-key-lu
AI_MODEL=gpt-4o-mini
PORT=5000
DEDUP_DAYS=14
```

## Menjalankan

```bash
.venv/bin/python app.py
# buka http://127.0.0.1:5000/login
```

- Kunjungan pertama = buat username + password admin
- Database `db.sqlite` auto-create + auto-migrasi kolom baru saat start
- Scheduler ikut start otomatis (cek tiap 5 menit)
- Login akun pertama: set `BROWSER_HEADLESS=false` dulu biar browser kelihatan kalau ada captcha/verif HP

## Cara Penggunaan

### 1. Setting AI (sekali saja)

Buka **Setting AI**: isi Base URL (default `https://api.openai.com/v1`), API Key (`sk-...`), Model (`gpt-4o-mini`). Protokol OpenAI-compatible — bisa diganti ke provider lain yang support `/chat/completions` cukup dengan ganti base URL + model. Klik **Simpan + Test koneksi** untuk verifikasi. Kalau API key dikosongkan, dipakai yang dari `.env`.

### 2. Tambah akun sosmed

Buka **Akun** → form **Hubungkan Akun Baru**:

**Cara A — import cookies (disarankan, tercepat):**

1. Install ekstensi [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) di Chrome
2. Buka Threads/IG/FB/X di tab yang **sudah login**
3. Klik ikon ekstensi → Copy/Export **JSON** (Netscape `.txt` juga bisa)
4. Di form: pilih platform + label + proxy (opsional), paste JSON (atau upload file), klik **Hubungkan + Test Cookies**
5. Sistem test otomatis: format valid? domain cocok dengan platform? cookies masih hidup (buka beranda headless, bukan redirect login)?
6. Lolos → akun `Tersambung Aktif`. Gagal → pesan spesifik (misal "cookies kedaluwarsa... login ulang lalu export lagi") dan akun dibatalkan

**Cara B — login manual via browser:**

1. Kosongkan kolom cookies, klik **Hubungkan**
2. Server bukakan Chromium ke halaman login platform itu
3. Login manual sampai beres (captcha/2FA/verif HP bebas), pastikan sampai beranda
4. Balik ke web → **Saya Sudah Login — Simpan Sesi**
5. Sesi nunggu maksimal 30 menit, lalu hangus otomatis

### 3. Atur akun (halaman Detail)

Klik **Detail** di kartu akun:

- **Persona**: nama, gaya bahasa, system prompt, 1 contoh cerita. Inilah yang menentukan gaya AI tiap akun
- **Pengaturan**: label, proxy (`http://user:pass@host:port`), post/hari, jam aktif
- **User-Agent**: dropdown 102 pilihan (Chrome/Edge/Firefox/Safari/Opera/Brave/Vivaldi/UC — desktop Windows 11/10/7, macOS, Linux/Ubuntu, iPhone, iPad, Android). Yang sudah dipakai akun lain **ditandai** (`dipakai: label-akun`) biar fingerprint tiap akun beda
- **Login Ulang / Pause / Hapus** (hapus ikut membersihkan persona, jobs, folder sesi)

### 4. Isi produk affiliate

Buka **Produk**: tambah manual (nama + link Shopee + deskripsi "ini produk apa" + kategori) atau **Import CSV** dengan header `nama,link_shopee,deskripsi,kategori`.

### 5. Generate & posting

- **Generate AI**: pilih akun + produk → AI bikin cerita 3–5 kalimat soft-selling (link disisip natural). Cocok → **Posting Sekarang**; kurang cocok → generate ulang
- **Dashboard**: post cepat manual (pilih akun, produk kosongkan = acak hindari dedup), riwayat 20 job, jadwal hari ini, performa per akun
- **Jadwal**: antrean queued, setting per akun (post/hari, jam), kuota hari ini per akun. Scheduler otomatis: tiap akun yang due → pilih produk belum dipost 14 hari → generate AI → posting 1-1 → screenshot bukti

### Alur bisnis singkat

```
Login → Setting AI → Hubungkan akun (cookies/login manual) → isi Persona
→ isi Produk → atur Jadwal → scheduler generate + posting otomatis
```

## Struktur Project

```
omnipost/
  app.py                 # Flask entry, semua route, start scheduler
  .env                   # config (jangan di-commit)
  .env.example           # contoh config
  requirements.txt
  db.sqlite              # SQLite (auto-create, jangan di-commit)
  core/
    db.py                # koneksi + schema + settings
    ai.py                # generate_story() via OpenAI-compatible client
    scheduler.py         # APScheduler: tick 5 mnt, jitter, dedup 14 hari
    login_session.py     # browser login manual persisten (token, TTL 30 mnt)
    cookie_import.py     # parse cookies (JSON/Netscape/header) + verify
    user_agents.py       # 102 UA + penanda pemakaian per akun
    poster/
      base.py            # launch browser + fallback Chromium, storage_state
      threads.py / instagram.py / facebook.py / twitter.py
  templates/             # Jinja: base, login, index, akun, akun_detail,
                         # akun_login, produk, persona, generate, jadwal, setting_ai
  static/
    css/app.css          # tema Vivid Pulse flat (tanpa CDN)
    fonts/               # Josefin Sans + Plus Jakarta Sans (lokal)
    icons/               # 27 Heroicon outline (lokal, sprite)
  storage/<id>/          # per akun: storage_state.json + shots/
  web_design/            # template desain acuan (bukan runtime)
```

## Troubleshooting

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| 500 saat Hubungkan + Test Cookies | Chromium belum terinstall (`Executable doesn't exist`) | `.venv/bin/python -m playwright install chromium`. Kode sudah ada fallback ke Chromium cache/sistem |
| Cookies "tidak works / dilempar ke login" | cookies basi atau salah tab | login ulang di browser, pastikan di tab yang sudah login, export ulang |
| Cookies "domain tidak cocok" | export dari situs lain | buka platform yang benar di tab login, baru export |
| Akun status error, posting gagal | sesi mati / kena logout platform | klik Login Ulang di detail akun |
| Generate gagal / test koneksi gagal | base URL / key / model salah | cek Setting AI → Test koneksi, pastikan model tersedia di provider |
| Scheduler tidak posting | di luar jam aktif / belum due / produk habis kena dedup | cek Jadwal: jam aktif, kuota, tambah produk baru |
| Browser login tidak nongol (VPS) | headless tanpa display | butuh VNC/RDP; atau pakai cara import cookies saja |

## Keamanan

- Single-user personal use, tanpa role. Ganti password default setelah install
- `SECRET_KEY` wajib random string di production
- Password akun sosmed **tidak disimpan** (login via cookies/sesi browser saja)
- Jangan commit `.env`, `db.sqlite`, `storage/` (sudah di `.gitignore`)
