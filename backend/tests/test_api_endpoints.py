"""Phase 4.5 API verification script."""

import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"


def get(path):
    try:
        r = urllib.request.urlopen(f"{BASE}{path}")
        return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def post(path, data):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


print("=" * 60)
print("Phase 4.5 Verification")
print("=" * 60)

# Test 1: Health endpoint with llm_provider field
print("\n[1] GET /health")
status, body = get("/health")
print(f"  Status: {status}")
print(f"  Body: {json.dumps(body, indent=2)}")
assert "llm_provider" in body, "MISSING: llm_provider field"
print("  >> PASS: llm_provider field present")

# Test 2: Oversized source code rejection
print("\n[2] POST /generate (oversized source)")
status, body = post("/generate", {
    "source_code": "x = 1\n" * 20000,  # ~120KB, exceeds 100KB schema limit
})
print(f"  Status: {status}")
if status == 422:
    print("  >> PASS: Oversized source rejected at schema level")
else:
    print(f"  >> Body: {json.dumps(body)[:200]}")

# Test 3: Normal generation (will fail without API key but tests full flow)
print("\n[3] POST /generate (normal, no API key)")
status, body = post("/generate", {
    "source_code": "def add(a, b):\\n    return a + b",
})
print(f"  Status: {status}")
print(f"  ID: {body.get('id', 'N/A')}")
print(f"  Status field: {body.get('status', 'N/A')}")
print(f"  Prompt version: {body.get('prompt_version', 'N/A')}")
print(f"  Duration ms: {body.get('duration_ms', 'N/A')}")
if body.get("error_message"):
    print(f"  Error: {body['error_message'][:100]}")

gen_id = body.get("id")

# Test 4: Get by ID - verify new fields
if gen_id:
    print(f"\n[4] GET /generations/{gen_id}")
    status, body = get(f"/generations/{gen_id}")
    print(f"  Status: {status}")
    print(f"  prompt_version: {body.get('prompt_version')}")
    print(f"  input_tokens: {body.get('input_tokens')}")
    print(f"  output_tokens: {body.get('output_tokens')}")
    print(f"  total_tokens: {body.get('total_tokens')}")
    print(f"  duration_ms: {body.get('duration_ms')}")

# Test 5: History with new fields
print("\n[5] GET /generations")
status, body = get("/generations")
print(f"  Status: {status}")
print(f"  Total: {body.get('total', 'N/A')}")

print("\n" + "=" * 60)
print("Phase 4.5 verification complete!")
print("=" * 60)
