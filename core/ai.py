import os
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


PROMPT_TEMPLATE = """{system_prompt}

Gaya bahasa: {gaya}
Contoh cerita (tirukan gayanya, jangan copy):
{contoh}

Produk yang mau diselipin:
- Nama: {nama}
- Deskripsi: {deskripsi}
- Link: {link}

Aturan:
- Cerita 3-5 kalimat, natural kayak postingan orang biasa, soft-selling, JANGAN kayak iklan.
- Sisipkan link secara natural di tengah cerita (misal: "aku tanya penjualnya... ternyata pake {link}").
- Wajib ada link-nya tepat 1x. Bahasa Indonesia santai.
"""

def generate_story(system_prompt, gaya, contoh, nama, deskripsi, link):
    _, _, model = _cfg()
    client = _client()
    user_msg = PROMPT_TEMPLATE.format(system_prompt=system_prompt, gaya=gaya or "-",
                                      contoh=contoh or "-", nama=nama,
                                      deskripsi=deskripsi or "-", link=link)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_msg}],
        temperature=0.9,
        max_tokens=300,
    )
    return resp.choices[0].message.content.strip()
