# Omnipost — Autopost Affiliate Shopee

Web app personal-use (single user) untuk auto-posting produk affiliate Shopee ke **Threads, Instagram, Facebook, dan X/Twitter**. Tanpa API resmi Meta/X — memakai **browser automation (Playwright + Chromium)** yang meniru manusia. **AI (OpenAI-compatible)** membuat cerita soft-selling yang disisipi link Shopee, mengikuti persona tiap akun. **Scheduler** jalan otomatis dengan jeda acak + jitter, dedup produk 14 hari, proxy & user-agent per akun. Performa tiap postingan (views, likes, komentar, repost, share) direkam otomatis, dan link Shopee bisa ditahan dulu — baru ditempel setelah postingan ramai.

## Fitur

- **Login personal** — single user, kunjungan pertama = buat akun
- **Kelola akun sosmed** — 2 cara menambah akun:
  - **Import cookies** (disarankan): install ekstensi [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc), export JSON di tab yang sudah login, paste/upload ke form — sistem langsung **test otomatis** (parse format → cek domain → buka beranda headless). Gagal = pesan jelas kenapa, akun sampah auto-dihapus
  - **Login manual via browser**: server bukakan Chromium ke halaman login, login manual (captcha/2FA bebas), klik simpan sesi
- **Detail akun** — klik Detail di tiap kartu: persona, pengaturan (label, proxy, jadwal), user-agent, riwayat 20 job, hapus akun
- **Persona per akun** (1 akun = 1 persona) — nama, **niche**, **profil (umur/kerjaan)**, gaya bahasa, system prompt, **3–5 contoh cerita bagus** (pisahkan dengan `---`), **larangan frasa** (ditegakkan validator, bukan cuma prompt), dan **contoh buruk** yang harus dihindari AI
- **Produk affiliate** — CRUD + import CSV (`nama,link_shopee,deskripsi,kategori`)
- **AI storytelling 3 bagian** — AI diminta balas JSON: `part1` (hook ≤40 karakter + cerita, tanpa link/produk), `part2` (bridge social proof + nama produk + satu manfaat), `reply_bait` (pertanyaan A-vs-B buat memancing balasan). **Link tidak dipegang AI** — kode yang menempel di akhir `part2`, jadi posisinya nggak mungkin salah
- **Anti-template** — 6 bentuk cerita diputar acak: spill produk setelah ditanya, narasi hari kerja, obrolan yang bikin penasaran, kejadian kecil, perbandingan sebelum-sesudah, kesalahan kecil + solusi. Bentuk disimpan di `jobs.story_shape`, dan bentuk yang dipakai 2 job terakhir otomatis dibuang dari pilihan
- **Dedup hook 14 hari** — hook (baris pertama part1) disimpan di `jobs.hook`. Sebelum tayang, hook dibandingkan dengan hook 14 hari terakhir akun itu (kemiripan teks ≥0.8 dihitung pakai `SequenceMatcher`). Mirip → generate ulang otomatis (maks 3x, bentuk cerita ikut diganti); tetap mirip → job `failed` dengan alasan, tidak tayang
- **Validator konten** — hasil AI dicek kode sebelum tayang: hook ≤40 karakter, part1 ≥180 karakter, tidak ada nominal harga (`Rp`, `50rb`, `1.000.000`), tidak ada kata terlarang (diskon, promo, murah, buruan, flash sale, wajib punya, pake produk ini, stok terbatas), tidak ada link di part1, dan part2 wajib menyebut nama produk. Gagal → retry maks 3x dengan feedback error dikirim balik ke AI; tetap gagal → job disimpan `failed` dan **tidak tayang**
- **Normalisasi otomatis** — kalau model menulis part1 satu baris panjang, kode memecah hook di batas kalimat/kata (≤40 karakter). `\n` yang ter-escape ganda juga dinormalisasi
- **Preview terstruktur** — halaman Generate AI menampilkan hasil per bagian (1/2, 2/2, pancingan balasan)
- **Setting AI** — protokol OpenAI-compatible (base URL + API key + model dari web UI, ada tombol **Muat daftar model** dari `GET /models`)
- **Rotasi topik cerita harian** — 24 topik keseharian diputar per akun; topik yang sudah dipakai <30 hari disimpan di `topic_history` dan dilewati. Kalau semua sudah terpakai, siklus diulang
- **Campuran konten: promosi + cerita harian** — tiap akun punya **Promosi (%)**. Persentase menentukan porsi postingan jualan vs cerita keseharian (curhat/observasi, tanpa produk & link). Dijaga anti-monoton: 2 promosi beruntun dipaksa jadi cerita, 2 cerita beruntun dipaksa promosi. Kalau produk habis kena dedup, otomatis jadi cerita (kalau dipaksa promosi, dapat pesan jelas)
- **Scheduler** — per akun: post/hari, jam aktif, cek tiap 5 menit + jitter 5–25 menit, dedup (akun+produk) 14 hari, antre 1-1 bergantian
- **Anti-spam** — proxy per akun + 102 pilihan user-agent (tanda mana yang sudah dipakai akun lain)
- **Bukti posting** — screenshot tiap job sukses/gagal di `storage/<id>/shots/`
- **Statistik per postingan** — views, likes, komentar, repost, share direkam otomatis: halaman `/statistik` berisi KPI total, tabel rincian per postingan, tombol perbarui (batch) dan cek ulang per baris. Scrape dari halaman Threads karena tidak ada API resmi
- **Link belakangan (mode ramai)** — postingan terbit tanpa link dulu; begitu views/likes lewat ambang yang kamu set, link Shopee otomatis ditempel sebagai self-reply (tanpa kartu preview). Dicek tiap 30 menit, jendela default 24 jam, status per job: `pending` → `added` / `expired`
- **Gaya thread bersih** — link masuk bagian ke-2 thread (`Add to thread`), kartu preview link selalu dihapus sebelum tombol Post diklik
- **Log error terstruktur** — setiap exception dapat ID unik (`ERR-HHMMSS-NNN`), traceback + konteks request tersimpan, bisa dibaca di halaman `/logs`

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

Buka **Setting AI**: isi Base URL (default `https://api.openai.com/v1`), API Key (`sk-...`), lalu Model.

- **Muat daftar model** — tombol ini memanggil `GET /models` di base URL pakai key yang diisi, lalu hasilnya disimpan sebagai pilihan dropdown (datalist) di kolom Model. Jumlah model yang ditemukan ditampilkan di label. Cocok buat provider/tunnel yang punya ratusan model — tinggal ketik buat nyari
- **Simpan + Test koneksi** — cek `/models` + satu chat completion kecil, lalu lapor base URL, model, jumlah model, dan durasi
- Kalau endpoint tidak punya `/models`, isi nama model manual tetap bisa
- Protokol OpenAI-compatible — bisa dipakai untuk provider apa pun yang support `/chat/completions`
- Kalau API key dikosongkan, dipakai yang dari `.env`

Pesan error dibuat spesifik: 401 (key ditolak), 402/403 (butuh saldo/paket), 404 (model tidak ada di endpoint — pakai Muat daftar model), 410 (model retired), 429 (kena limit), timeout/koneksi gagal.

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

- **Persona**: nama, niche, profil (umur/kerjaan), gaya bahasa, system prompt, 3–5 contoh cerita bagus, larangan frasa, dan contoh buruk. Inilah yang menentukan gaya AI tiap akun, termasuk cerita kesehariannya. Larangan frasa ikut dicek validator — kalau AI tetap memakainya, hasil ditolak dan digenerate ulang
- **Pengaturan**: label, proxy (`http://user:pass@host:port`), post/hari, jam aktif, **Promosi (%)** (0 = semua cerita harian, 100 = semua promosi, default 70)
- **User-Agent**: dropdown 102 pilihan (Chrome/Edge/Firefox/Safari/Opera/Brave/Vivaldi/UC — desktop Windows 11/10/7, macOS, Linux/Ubuntu, iPhone, iPad, Android). Yang sudah dipakai akun lain **ditandai** (`dipakai: label-akun`) biar fingerprint tiap akun beda
- **Login Ulang / Pause / Hapus** (hapus ikut membersihkan persona, jobs, folder sesi)

### 4. Isi produk affiliate

Buka **Produk**: tambah manual (nama + link Shopee + deskripsi "ini produk apa" + kategori) atau **Import CSV** dengan header `nama,link_shopee,deskripsi,kategori`.

### 5. Generate & posting

- **Generate AI**: pilih akun + **tipe konten** (Promosi produk / Cerita keseharian) lalu produk. Untuk promosi, AI bikin 3 bagian: **part1** (hook ≤40 karakter + cerita sensorik 4–6 kalimat, tanpa produk/link), **part2** (bridge social proof + nama produk + satu manfaat), **reply_bait** (pertanyaan A-vs-B). Link ditempel kode di akhir part2. Cocok → **Posting Sekarang**; kurang cocok → generate ulang
- **Dashboard**: post cepat manual (pilih akun, produk kosongkan = acak hindari dedup), riwayat 20 job, jadwal hari ini, performa per akun
- **Jadwal**: antrean queued, setting per akun (post/hari, jam), kuota hari ini per akun. Scheduler otomatis: tiap akun yang due → pilih produk belum dipost 14 hari → generate AI → posting 1-1 → screenshot bukti

### 6. Statistik & link belakangan

Buka **Statistik** (sidebar). Isinya:

- **KPI**: total views, total likes, total komentar, repost + share
- **Tabel rincian**: waktu terbit, akun, produk, status link, views, likes, komentar, repost, share, waktu terakhir dicek
- **Perbarui Metrik** — ambil ulang semua postingan yang due (batch)
- **Cek** per baris — ambil ulang satu postingan saja

Angka diambil dengan membuka profil (untuk dapat URL post) lalu halaman postingan. Format `1,2 rb` / `1.2K` / `1,2 jt` otomatis dinormalisasi jadi integer.

**Mode link belakangan** (kartu "Link Otomatis Saat Ramai"):

| Kolom | Arti |
|---|---|
| Aktifkan mode | Kalau dicentang, postingan berikutnya terbit **tanpa** link |
| Metrik pemicu | `Views` atau `Likes` |
| Ambang | Nilai minimal sebelum link ditempel (contoh: 100) |
| Jendela (jam) | Batas waktu sejak posting (1–168 jam, default 24) |

Alur: posting cerita → status `pending` → scheduler cek tiap 30 menit (metrik di-refresh kalau sudah basi >30 menit) → kalau tembus ambang, link ditempel sebagai self-reply → status `added`. Kalau lewat jendela tanpa tembus ambang → `expired`, link tidak dipasang lagi.

Catatan: AI tetap menyisipkan link di caption, tapi saat mode aktif link itu **dibuang dari postingan utama** dan baru dipakai waktu ditempel. Kalau mau balik ke gaya lama (link langsung di bagian ke-2 thread), cukup hilangkan centang "Aktifkan mode link belakangan".

### Alur bisnis singkat

```
Login → Setting AI → Hubungkan akun (cookies/login manual) → isi Persona
→ isi Produk → atur Jadwal → scheduler generate + posting otomatis
```

### Catatan teknis Threads (penting)

- **"Add to thread" cuma ada saat bikin thread.** Setelah posting, menu `...` hanya berisi Insights, Copy link, Get embed code, Save, Pin reply, Archive, Hide like and share counts, Reply options, Delete. Jadi link belakangan memakai jalur **reply ke postingan sendiri** (self-reply), yang tidak ada batas waktunya
- **Batas edit post**: 15 menit (5 menit di versi awal)
- **Link tanpa kartu preview**: kartu OG dibuat async. Kode menunggu kartu muncul, menghapusnya (maks 2 percobaan), memverifikasi hilang, baru klik Post. Kalau kartu bandel, fallback: post teks saja + link di reply
- **Ketik pakai CDP `Input.insertText`**, bukan `keyboard.type` per karakter (spasi hilang) atau set `innerText` (diabaikan React). Klik tombol pakai `Input.dispatchMouseEvent` dengan koordinat yang di-resolve ulang setelah layout geser
- **Threads web saat ini pakai `div[data-pressable-container="true"]`**, bukan `<article>` — selector di `core/metrics.py` mengikuti itu

## Jadwal internal scheduler

| Tugas | Interval | Yang dikerjakan |
|---|---|---|
| `tick` | 5 menit | cek akun yang due (jam aktif, jeda 24/post_per_hari + jitter 5–25 menit, dedup 14 hari) → tentukan tipe (promosi/cerita) → generate AI → posting |
| `autolink_check` | 30 menit | postingan `pending` yang sudah ramai → tempel link sebagai self-reply |
| `refresh_all` (metrik) | 3 jam | ambil views/likes/komentar/repost/share untuk maks 8 post, umur ≤14 hari |
| `refresh_all_sessions` | 6 jam | cek sesi akun, cek yang terakhir dicek >20 jam |

Semua tugas browser memakai satu `LOCK` global — posting dan scraping tidak pernah jalan bersamaan.

## Data & Database

| Tabel | Isi |
|---|---|
| `user` | akun login panel (single user) |
| `social_accounts` | akun sosmed: platform, label, proxy, username asli, user-agent, status sesi, jadwal, `promo_ratio` |
| `personas` | 1 persona per akun: nama, `niche`, `profil`, gaya bahasa, system prompt, contoh cerita (multi, dipisah `---`), `larangan`, `contoh_buruk` |
| `topic_history` | topik cerita harian yang sudah dipakai per akun (`topic`, `used_at`) untuk rotasi 30 hari |
| `products` | produk affiliate: nama, link Shopee, deskripsi, kategori, aktif |
| `jobs` | satu baris tiap postingan: `post_type` (`promo`/`story`), `story_shape` (bentuk cerita yang dipakai), `hook` (baris pertama part1 untuk dedup), `part1`, `part2`, `reply_bait`, caption gabungan, status, `posted_at`, `screenshot_path`, `error`, `link_status`, `link_added_at`. `product_id` NULL untuk cerita harian |
| `post_metrics` | metrik per job (unik 1 baris/job): `post_url`, views, likes, replies, reposts, shares, `checked_at`, `error` |
| `settings` | key-value: config AI (`ai_base_url`, `ai_api_key`, `ai_model`, cache `ai_models`) + `autolink_enabled/metric/threshold/window_hours` |

Semua kolom baru ditambahkan otomatis lewat migrasi `init_db()` saat start — aman untuk database lama.

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
    scheduler.py         # APScheduler: tick 5 mnt, autolink 30 mnt, dedup 14 hari
    metrics.py           # scrape views/likes/komentar/repost/share per postingan
    session_guard.py     # refresh sesi berkala + deteksi sesi mati
    errorlog.py          # ID error unik, traceback, rotasi log 2 MB
    login_session.py     # browser login manual persisten (token, TTL 30 mnt)
    cookie_import.py     # parse cookies (JSON/Netscape/header) + verify
    user_agents.py       # 102 UA + penanda pemakaian per akun
    poster/
      __init__.py        # router platform + flow Threads (CDP, hapus preview, autolink reply)
      base.py            # launch browser + fallback Chromium, storage_state
      threads.py / instagram.py / facebook.py / twitter.py # poster per platform
  templates/             # Jinja: base, login, index, akun, akun_detail, akun_login,
                         # produk, generate, jadwal, statistik, setting_ai, logs, error
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
| Generate gagal / test koneksi gagal | base URL / key / model salah | cek Setting AI → **Muat daftar model**, pilih model dari daftar, lalu Test koneksi |
| Test AI: "Model tidak tersedia di endpoint ini (404)" | nama model tidak ada di provider (contoh `gpt-4o-mini` di tunnel yang cuma punya `gpt-oss-120b`) | klik **Muat daftar model**, pilih salah satu dari dropdown |
| Test AI: "API key ditolak (401)" | key salah / kadaluarsa / bukan untuk base URL itu | cek ulang key dan base URL |
| Test AI: "butuh saldo/paket (402/403)" | model berbayar di provider itu | pilih model gratis atau isi saldo |
| Test AI: model retired (410) | model sudah dipensiunkan provider | pilih model lain dari daftar |
| Scheduler tidak posting | di luar jam aktif / belum due / produk habis kena dedup | cek Jadwal: jam aktif, kuota, tambah produk baru |
| Browser login tidak nongol (VPS) | headless tanpa display | butuh VNC/RDP; atau pakai cara import cookies saja |
| Metrik 0 semua / "postingan tidak ketemu" | caption postingan berbeda jauh dari data job, atau post sudah dihapus | klik **Cek** per baris; kalau post memang dihapus, angkanya akan tetap 0 |
| Metrik tidak update | semua post baru saja dicek (<3 jam) | tunggu putaran berikutnya atau klik **Perbarui Metrik** |
| Link tidak nempel padahal ramai | mode belum diaktifkan, metrik belum refresh, atau lewat jendela | cek kartu "Link Otomatis Saat Ramai"; status `expired` artinya lewat batas waktu |
| Caption AI jadi satu blok panjang / bukan 3 bagian | model tidak balas JSON valid atau JSON terpotong | kode retry 3x dengan feedback; kalau tetap gagal, job jadi `failed` dan tidak tayang. Naikkan `max_tokens` atau ganti model kalau sering |
| Cerita harian terasa berulang | topik sudah dipakai <30 hari | sistem otomatis melewati topik di `topic_history`; tambah topik baru di `DAILY_TOPICS` (`core/ai.py`) |
| Job `failed` dengan alasan "hook mirip postingan 14 hari terakhir" | AI berkali-kali bikin hook yang mirip | sistem coba 3x dengan bentuk berbeda; generate manual dari halaman Generate untuk lihat hook-nya, atau tunggu >14 hari |
| Cerita terasa itu-itu saja | bentuk cerita (shape) dipakai berulang | shape dipilih acak dan 2 bentuk terakhir dibuang otomatis; kalau masih monoton, tambah variasi di `STORY_SHAPES` (`core/ai.py`) |
| Job `failed` dengan alasan "validasi konten gagal" | AI melanggar aturan (harga/kata promo/hook panjang/produk tidak disebut) | lihat pesan error di riwayat job. Generate ulang; kalau konsisten, perbaiki system prompt persona atau deskripsi produk |
| Hook part1 kepanjangan (>40 karakter) | model mengabaikan aturan hook | kode memecah hook otomatis di batas kalimat/kata; retry juga memberi feedback eksplisit |
| Tombol Post disabled di Threads | kartu preview link masih render | kode menunggu kartu muncul, menghapusnya, lalu resolve ulang koordinat Post; kalau tetap gagal, fallback ke post teks + link di reply |

## Keamanan

- Single-user personal use, tanpa role. Ganti password default setelah install
- `SECRET_KEY` wajib random string di production
- Password akun sosmed **tidak disimpan** (login via cookies/sesi browser saja)
- Jangan commit `.env`, `db.sqlite`, `storage/` (sudah di `.gitignore`)
