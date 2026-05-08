import urllib.request
import json

# Test accessing produccion endpoint WITHOUT token
req = urllib.request.Request(
    "http://127.0.0.1:8000/produccion/plantillas",
    method="GET"
)

try:
    with urllib.request.urlopen(req) as response:
        print("FAIL: Should have returned 401, got:", response.status)
except urllib.error.HTTPError as e:
    if e.code == 401:
        print("PASS: Got 401 Unauthorized (DummyUser removed correctly)")
    else:
        print(f"FAIL: Expected 401, got {e.code}")
except Exception as e:
    print(f"ERROR: {e}")