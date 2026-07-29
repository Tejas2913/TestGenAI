"""Quick Phase 4.5 endpoint verification."""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"

def req(method, path, data=None):
    url = f"{BASE}{path}"
    if method == "GET":
        r = urllib.request.urlopen(url)
        return r.status, json.loads(r.read().decode())
    body = json.dumps(data).encode()
    rq = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(rq)
        return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

# 1. Health
s, b = req("GET", "/health")
print(f"[1] Health: {s} -> {json.dumps(b)}")

# 2. Oversized source
big = "x = 1\n" * 20000
s, b = req("POST", "/generate", {"source_code": big})
print(f"[2] Oversized: {s} -> rejected={s==422}")

# 3. Normal generation
s, b = req("POST", "/generate", {"source_code": "def add(a, b):\n    return a + b"})
print(f"[3] Generate: {s} -> status={b.get('status')} prompt_v={b.get('prompt_version')} dur={b.get('duration_ms')}")
gid = b.get("id")

# 4. Get by ID
if gid:
    s, b = req("GET", f"/generations/{gid}")
    print(f"[4] Get: {s} -> tokens=({b.get('input_tokens')},{b.get('output_tokens')},{b.get('total_tokens')})")

print("\nDone!")
