import os
import re
import random
from openai import OpenAI

def _cfg():
    from core.db import get_setting
    base_url = get_setting("ai_base_url", "") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    api_key = get_setting("ai_api_key", "") or os.getenv("OPENAI_API_KEY", "")
    model = get_setting("ai_model", "") or os.getenv("AI_MODEL", "gpt-4o-mini")
    return base_url, api_key, model

def _client():
    base_url, api_key, _ = _cfg()
    return OpenAI(base_url=base_url, api_key=api_key)


def list_models(base_url=None, api_key=None, timeout=25):
    base_url = base_url or _cfg()[0]
    api_key = api_key or _cfg()[1]
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    resp = client.models.list()
    ids = []
    for m in resp.data:
        mid = getattr(m, "id", None)
        if mid:
            ids.append(mid)
    return sorted(set(ids))


def test_connection(timeout=60):
    import time
    base_url, api_key, model = _cfg()
    client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    started = time.time()
    models = []
    try:
        models = [m.id for m in client.models.list().data]
    except Exception:  # noqa: BLE001
        models = []
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Balas satu kata: halo"}],
        max_tokens=30,
    )
    return {
        "base_url": base_url,
        "model": model,
        "models": len(models),
        "seconds": round(time.time() - started, 2),
        "reply": (resp.choices[0].message.content or "").strip(),
    }


STORY_SHAPES = [
    "spill produk setelah ditanya orang",
    "narasi hari kerja + satu detail produk nyempil",
    "obrolan dengan orang lain yang bikin penasaran",
    "kejadian kecil yang bikin sadar butuh barang itu",
    "perbandingan sebelum-sesudah",
    "kesalahan kecil yang akhirnya ketemu solusinya",
]

PROMPT_TEMPLATE = """{system_prompt}

Gaya bahasa: {gaya}
Contoh cerita (tirukan gayanya, jangan copy):
{contoh}

Produk:
- Nama: {nama}
- Deskripsi: {deskripsi}

Bentuk cerita yang WAJIB dipakai (jangan nyimpang): {shape}

Balas HANYA dengan JSON valid, tanpa markdown:
{{"part1": "...", "part2": "...", "reply_bait": "..."}}

ATURAN part1 (cerita, TANPA link, TANPA produk):
- Baris pertama = hook, MAKSIMAL 40 karakter, bikin orang pengen buka "lihat selengkapnya"
- Total 4-6 kalimat, ada detail sensorik konkret (bau, suhu, bunyi, tekstur)
- Detail WAJIB logis dengan setting cerita
- Jangan pakai "dia" kalau belum disebut siapa
- DILARANG: link, nama produk, harga, angka rupiah

ATURAN part2 (bridge + FAB):
- Kalimat 1: social proof nyambung dari part1 (contoh: "yang tadi nanya ...")
- Kalimat 2: nama produk + SATU manfaat konkret
- DILARANG menyebut harga, nominal, diskon, atau kata promo
- DILARANG frasa: "pake produk ini", "wajib punya", "buruan", "murah"

ATURAN reply_bait:
- Isi pertanyaan A-vs-B yang bikin orang jawab, contoh "kamu tim X apa tim Y?"
- DILARANG pertanyaan mati seperti "menurut kalian gimana?"
- Kalau tidak perlu, isi string kosong ""
"""


def _parse_parts(raw, strict=False):
    import json as _json
    import re as _re
    text = (raw or "").strip()
    if text.startswith("```"):
        text = _re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = _re.sub(r"\s*```$", "", text).strip()
    data = None
    try:
        data = _json.loads(text)
    except ValueError:
        i, j = text.find("{"), text.rfind("}")
        if i >= 0 and j > i:
            try:
                data = _json.loads(text[i:j + 1])
            except ValueError:
                data = None
    if isinstance(data, dict):
        def _unfold(t):
            t = str(t or "").strip()
            if "\\n" in t or "\\t" in t:
                t = t.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
            return t
        part1 = _unfold(data.get("part1"))
        part2 = _unfold(data.get("part2"))
        bait = _unfold(data.get("reply_bait"))
        if bait.lower() in ('""', "''", "-", "tidak", "none", "null"):
            bait = ""
        if part1:
            return part1, part2, bait
    if strict:
        return None, None, None
    blocks = [b.strip() for b in (raw or "").split("\n\n") if b.strip()]
    part1 = blocks[0] if blocks else (raw or "").strip()
    part2 = blocks[1] if len(blocks) > 1 else ""
    return part1, part2, ""


BANNED = ["diskon", "promo", "murah", "buruan", "flash sale",
          "wajib punya", "pake produk ini", "stok terbatas"]

_PRICE_RE = re.compile(r"\b\d{1,3}(\.\d{3})+\b|\bRp\s?\d|\b\d+\s?(rb|ribu|k)\b", re.I)


class StoryValidationError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_story(part1, part2, nama_produk="", ):
    errs = []
    part1 = part1 or ""
    part2 = part2 or ""
    hook = part1.split("\n")[0].strip()
    if len(hook) > 40:
        errs.append(f"hook {len(hook)} char, maks 40")
    if len(part1) < 180:
        errs.append("part1 terlalu tipis (min 180 char)")
    if _PRICE_RE.search(part1 + " " + part2):
        errs.append("ada nominal harga")
    both = (part1 + " " + part2).lower()
    for w in BANNED:
        if w in both:
            errs.append(f"kata terlarang: {w}")
    if "http" in part1.lower():
        errs.append("link bocor ke part1")
    if nama_produk:
        first = nama_produk.split()[0].lower()
        if first not in part2.lower():
            errs.append(f"part2 tidak menyebut produk ({first})")
    return errs


def _enforce_hook(part1, limit=40):
    text = (part1 or "").strip()
    if not text:
        return text
    first, _, rest = text.partition("\n")
    first = first.strip()
    if len(first) <= limit:
        return text
    body = (first + ("\n" + rest if rest else "")).strip()
    m = re.match(r"^(.+?[.!?])\s+", body)
    if m and len(m.group(1)) <= limit:
        hook = m.group(1)
        remainder = body[m.end():].strip()
    else:
        cut = body.rfind(" ", 0, limit)
        if cut <= 10:
            cut = limit
        hook = body[:cut].strip().rstrip(",;:-")
        remainder = body[cut:].strip()
    if not remainder:
        return hook
    return hook + "\n" + remainder


def _hook_too_long(part1, limit=40):
    first = (part1.split("\n")[0] or "").strip()
    return len(first) > limit


def generate_story(system_prompt, gaya, contoh, nama, deskripsi, link=None, shape=None):
    import logging
    _, _, model = _cfg()
    client = _client()
    user_msg = PROMPT_TEMPLATE.format(system_prompt=system_prompt, gaya=gaya or "-",
                                      contoh=contoh or "-", nama=nama,
                                      deskripsi=deskripsi or "-",
                                      shape=shape or random.choice(STORY_SHAPES))
    base_msgs = [{"role": "user", "content": user_msg}]
    best = None
    last_errs = []
    for attempt in range(3):
        msgs = list(base_msgs)
        if attempt > 0:
            msgs.append({"role": "assistant", "content": '{"part1": "'})
            msgs.append({"role": "user", "content":
                         "Perbaiki: " + "; ".join(last_errs) +
                         ". Balas ulang HANYA JSON valid dengan format yang sama, tanpa markdown."})
        resp = client.chat.completions.create(
            model=model,
            messages=msgs,
            temperature=max(0.4, 0.9 - attempt * 0.2),
            max_tokens=2500,
        )
        part1, part2, bait = _parse_parts(resp.choices[0].message.content or "", strict=True)
        if part1 and part2:
            part1 = _enforce_hook(part1)
        if not part1 or not part2:
            errs = ["JSON tidak valid atau terpotong (part1/part2 kosong)"]
            last_errs = errs
            logging.getLogger("omnipost").info("generate_story attempt %d: %s", attempt + 1, errs[0])
            continue
        errs = validate_story(part1, part2, nama)
        if not errs:
            return part1, part2, bait
        last_errs = errs
        if part1 and part2 and best is None:
            best = (part1, part2, bait)
        logging.getLogger("omnipost").info(
            "generate_story attempt %d gagal validasi: %s", attempt + 1, "; ".join(errs))
    raise StoryValidationError(last_errs or ["hasil AI tidak valid"])


DAILY_TOPICS = [
    "pagi hari yang riweuh sebelum berangkat kerja",
    "hujan tiba-tiba pas lagi di jalan",
    "makanan warung pinggir jalan yang bikin nagih",
    "antre panjang di minimarket",
    "drama kecil di grup chat keluarga",
    "keingetan mantan gara-gara lagu di radio",
    "kerjaan numpuk tapi pengen rebahan",
    "belanja online yang ternyata nggak sesuai foto",
    "tetangga yang suka banget nanya urusan orang",
    "malam minggu yang ternyata cuma di rumah",
    "kopi pagi yang rasanya beda kalau lagi males",
    "niat olahraga tapi batal di tengah jalan",
    "obrolan random sama tukang parkir",
    "cuaca panas yang bikin emosi naik",
    "nemu uang di kantong jaket lama",
    "lihat kucing liar yang gemesin",
    "nonton film yang endingnya bikin kesel",
    "gagal move on dari serial lama",
    "resign mental tiap hari Senin",
    "memikirkan harga barang yang makin naik",
    "trauma masa kecil yang tiba-tiba keinget",
    "rencana liburan yang cuma jadi wacana",
    "masak sendiri dan hasilnya nggak sesuai ekspektasi",
    "dengerin musik lama sambil mellow",
]

DAILY_TEMPLATE = """{system_prompt}

Gaya bahasa: {gaya}
Contoh cerita (tirukan gayanya, jangan copy):
{contoh}

Tulis satu postingan Threads tentang: {topik}

Aturan:
- 2-4 kalimat, natural kayak orang curhat atau observasi kecil, bukan jualan.
- JANGAN sebut produk, harga, brand, atau link apa pun.
- Boleh diakhiri pertanyaan ringan atau ajakan ngobrol biar orang balas.
- Bahasa Indonesia santai, sesuai gaya di atas.
"""

def generate_daily_story(system_prompt, gaya, contoh, topik=None):
    _, _, model = _cfg()
    client = _client()
    topik = topik or random.choice(DAILY_TOPICS)
    user_msg = DAILY_TEMPLATE.format(system_prompt=system_prompt, gaya=gaya or "-",
                                     contoh=contoh or "-", topik=topik)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_msg}],
        temperature=0.95,
        max_tokens=800,
    )
    return resp.choices[0].message.content.strip()
