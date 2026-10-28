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
