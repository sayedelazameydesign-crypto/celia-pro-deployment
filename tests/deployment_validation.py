#!/usr/bin/env python3
"""
celia.pro — Comprehensive Deployment Validation Suite
=====================================================
Runs against a live Cloud Run backend URL.
Usage:
    python3 tests/deployment_validation.py https://<service>.a.run.app

No secrets required (registration + login create their own credentials).
Outputs PASS/FAIL per test with latency metrics.
"""

import json
import sys
import time
import urllib.request
import urllib.error
import ssl
import concurrent.futures
from urllib.parse import urlencode

BASE = ""
TIMEOUT = 30
RESULTS = []


def req(method, path, payload=None, headers=None, expect_status=None):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(
        url, data=data, method=method,
        headers={**(headers or {}), "Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(r, timeout=TIMEOUT)
        body = resp.read().decode()
        latency = (time.time() - t0) * 1000
        try:
            return resp.status, latency, json.loads(body), dict(resp.headers)
        except json.JSONDecodeError:
            return resp.status, latency, body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        latency = (time.time() - t0) * 1000
        body = e.read().decode()
        try:
            return e.code, latency, json.loads(body), dict(e.headers)
        except json.JSONDecodeError:
            return e.code, latency, body, dict(e.headers)
    except Exception as e:
        return 0, (time.time() - t0) * 1000, {"error": str(e)}, {}


def report(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def main():
    global BASE
    if len(sys.argv) < 2:
        print("Usage: python3 deployment_validation.py https://<service>.a.run.app [email password]")
        sys.exit(1)
    BASE = sys.argv[1].rstrip("/")
    email = sys.argv[2] if len(sys.argv) > 2 else f"deploytest{int(time.time())}@celia.test"
    username = f"dt{int(time.time())}"
    password = sys.argv[3] if len(sys.argv) > 3 else f"Tst-{int(time.time())}-xY9!qW"

    print(f"=== celia.pro Deployment Validation Suite ===")
    print(f"Target: {BASE}\n")

    # 1. Health
    st, lat, body, _ = req("GET", "/api/health")
    db_status = body.get("components", {}).get("database", {}).get("status") if isinstance(body, dict) else None
    llm_status = body.get("components", {}).get("llm", {}).get("status") if isinstance(body, dict) else None
    # /api/health reports database=healthy once engine init succeeded; a real
    # connectivity proof is the register/login flow (section 3) writing to DB.
    report("Health endpoint (200 + JSON)", st == 200 and isinstance(body, dict),
           f"status={st} latency={lat:.0f}ms")
    report("Database component reported healthy", db_status == "healthy",
           f"database={db_status} llm={llm_status}")

    # 2. CORS
    st, lat, _, hdrs = req("OPTIONS", "/api/chat", headers={
        "Origin": "https://cerulean-boba-48f59a.netlify.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization",
    })
    acao = hdrs.get("access-control-allow-origin", "")
    acam = hdrs.get("access-control-allow-methods", "")
    acac = hdrs.get("access-control-allow-credentials", "")
    report("CORS preflight Origin", "cerulean-boba" in acao or acao == "*", f"ACAO={acao}")
    report("CORS preflight methods", "POST" in acam.upper() or "*" in acam, f"ACAM={acam}")
    report("CORS credentials header", acac.lower() == "true" or acac != "", f"ACAC={acac}")

    # 3. Auth flow
    st, lat, body, _ = req("POST", "/api/auth/register", {"email": email, "username": username, "password": password})
    registered = st in (200, 201, 409)  # 409 = already exists (ok if re-run)
    report("Register", registered, f"status={st} latency={lat:.0f}ms")

    st, lat, body, _ = req("POST", "/api/auth/login", {"email": email, "password": password})
    token = None
    if isinstance(body, dict):
        token = body.get("access_token") or body.get("token") or body.get("data", {}).get("access_token")
    report("Login → JWT token", st == 200 and bool(token),
           f"status={st} token_len={len(token) if token else 0}")

    auth_h = {"Authorization": f"Bearer {token}"} if token else {}
    st, lat, body, _ = req("GET", "/api/auth/me", headers=auth_h)
    report("JWT token validation (/me)", st == 200 if token else False, f"status={st}")

    # 4. Protected endpoint without token
    st, lat, _, _ = req("GET", "/api/auth/me")
    report("Auth required (no token → 401)", st == 401, f"status={st}")

    # 5. Agent chat (actual endpoint: /api/chat)
    if token:
        st, lat, body, _ = req("POST", "/api/chat", {
            "message": "مرحبا، هذا اختبار نشر — رد بجملة واحدة فقط.",
        }, headers=auth_h)
        reply_ok = st == 200 and isinstance(body, dict) and bool(body.get("response") or body.get("reply") or body.get("message"))
        report("Agent chat (/api/chat)", reply_ok, f"status={st} latency={lat:.0f}ms")
        if not reply_ok and isinstance(body, dict):
            print(f"      chat body: {json.dumps(body, ensure_ascii=False)[:300]}")
        # SLA
        report("Latency SLA < 15s (incl. cold start)", lat < 15000, f"latency={lat:.0f}ms")

    # 6. DB persistence: read back conversations via /api/auth/me or chat history
    if token:
        st, lat, body, _ = req("GET", "/api/conversations", headers=auth_h)
        if st == 200 and isinstance(body, dict) and "conversations" in body:
            convs = body.get("conversations", [])
        elif isinstance(body, list):
            convs = body
        else:
            convs = []
        report("Conversations read (DB persistence)", st == 200, f"status={st} count={len(convs)}")

    # 7. Error handling (empty message fails validation → 422)
    st, lat, body, _ = req("POST", "/api/chat", {"message": ""}, headers=auth_h)
    report("Empty message → 400/422", st in (400, 422), f"status={st}")

    # 8. Concurrent requests
    if token:
        def burst(i):
            s, l, b, h = req("GET", "/api/health")
            return s
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            codes = list(ex.map(burst, range(5)))
        report("Concurrent 5×/api/health", all(c == 200 for c in codes), f"codes={codes}")

    # Summary
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n=== SUMMARY: {passed}/{total} passed ===")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  ⚠ FAILED: {name} {detail}")
    if passed == total:
        print("\n🎉 DEPLOYMENT STATUS: PASS")
    else:
        print("\n❌ DEPLOYMENT STATUS: FAIL (see warnings above)")


if __name__ == "__main__":
    main()
