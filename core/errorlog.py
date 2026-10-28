import os
import re
import traceback
from collections import deque
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERROR_LOG = os.path.join(BASE_DIR, "error.log")
MAX_BYTES = 2 * 1024 * 1024
BACKUPS = 3

_counter = [0]

def _next_id():
    _counter[0] += 1
    ms = datetime.now().strftime("%H%M%S")
    return f"ERR-{ms}-{_counter[0]:03d}"

def _rotate():
    try:
        if not os.path.exists(ERROR_LOG) or os.path.getsize(ERROR_LOG) < MAX_BYTES:
            return
        oldest = f"{ERROR_LOG}.{BACKUPS}"
        if os.path.exists(oldest):
            os.remove(oldest)
        for i in range(BACKUPS - 1, 0, -1):
            src = f"{ERROR_LOG}.{i}" if i > 1 else ERROR_LOG
            dst = f"{ERROR_LOG}.{i + 1}" if i + 1 > 1 else ERROR_LOG
            if i == 1:
                src, dst = ERROR_LOG, f"{ERROR_LOG}.1"
            else:
                src, dst = f"{ERROR_LOG}.{i - 1}", f"{ERROR_LOG}.{i}"
            if os.path.exists(src):
                os.rename(src, dst)
    except Exception:  # noqa: BLE001
        pass

def log_error(where, e, ctx=None):
    eid = _next_id()
    tb = traceback.format_exc()[-4000:] if traceback.format_exc() != "NoneType: None\n" else ""
    line = [f"[{datetime.now().isoformat()}] {eid} {where} | {type(e).__name__}: {e}"]
    if ctx:
        line.append(f"  ctx: {ctx}")
    if tb:
        line.append(tb.rstrip())
    line.append("-" * 60)
    try:
        _rotate()
        with open(ERROR_LOG, "a") as f:
            f.write("\n".join(line) + "\n")
    except Exception:  # noqa: BLE001
        pass
    return eid

_ENTRY = re.compile(r"^\[(?P<ts>[^\]]+)\] (?P<eid>ERR-\S+) (?P<where>\S+) \| (?P<type>[^:]+): (?P<msg>.*)$")

def read_entries(limit=100):
    paths = [ERROR_LOG] + [f"{ERROR_LOG}.{i}" for i in range(1, BACKUPS + 1)]
    entries = []
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            continue
        cur = None
        for ln in lines:
            m = _ENTRY.match(ln.rstrip("\n"))
            if m:
                if cur:
                    entries.append(cur)
                cur = {"ts": m.group("ts"), "id": m.group("eid"), "where": m.group("where"),
                       "type": m.group("type"), "msg": m.group("msg"), "ctx": "", "tb": []}
            elif cur is not None:
                if ln.startswith("  ctx: "):
                    cur["ctx"] = ln[8:].strip()
                elif ln.rstrip("\n") == "-" * 60:
                    entries.append(cur)
                    cur = None
                else:
                    cur["tb"].append(ln.rstrip("\n"))
        if cur:
            entries.append(cur)
    entries.sort(key=lambda e: e["ts"], reverse=True)
    return entries[:limit]

def get_entry(eid):
    for e in read_entries(limit=2000):
        if e["id"] == eid:
            return e
    return None

def clear_log():
    for i in range(1, BACKUPS + 1):
        try:
            os.remove(f"{ERROR_LOG}.{i}")
        except OSError:
            pass
    try:
        open(ERROR_LOG, "w").close()
    except OSError:
        pass

def tail_raw(n=200):
    if not os.path.exists(ERROR_LOG):
        return ""
    with open(ERROR_LOG, errors="ignore") as f:
        return "".join(deque(f, n))
