#!/bin/bash
# =====================================================================
# celia.pro — API Key Verification Script
# Tests Gemini (free tier) and HuggingFace Inference API keys.
# Runs in the deployed hosting environment AFTER keys are added as env vars.
# Usage: export GEMINI_API_KEY=... HF_TOKEN=... && ./test_api_keys.sh
# =====================================================================
set -u

GEMINI_API_KEY="${GEMINI_API_KEY:-}"
HF_TOKEN="${HF_TOKEN:-}"
PASS=0; FAIL=0

green(){ echo -e "\033[32m$1\033[0m"; }
red(){ echo -e "\033[31m$1\033[0m"; }

# ---------- Gemini API ----------
echo "=== Testing Google Gemini API (free tier) ==="
if [ -z "$GEMINI_API_KEY" ]; then
  red "GEMINI_API_KEY not set. Skipping."
  FAIL=$((FAIL+1))
else
  RESP=$(curl -s -w "\n%{http_code}" "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY")
  HTTP=$(echo "$RESP" | tail -1)
  if [ "$HTTP" = "200" ]; then
    green "Gemini API key OK (HTTP 200, models listed)"
    PASS=$((PASS+1))
  else
    red "Gemini API key FAILED (HTTP $HTTP)"
    echo "$RESP" | head -3
    FAIL=$((FAIL+1))
  fi
  # Optional lightweight generation test (consumes free-tier quota)
  if [ "${LIVE_TEST:-0}" = "1" ]; then
    echo "-- Live generation test (gemini-2.5-flash)..."
    GRES=$(curl -s -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GEMINI_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"contents":[{"parts":[{"text":"Say OK in one word"}]}]}')
    if echo "$GRES" | grep -q "OK"; then
      green "Gemini live generation: OK"
    else
      red "Gemini live generation: FAILED"
      echo "$GRES" | head -2
      FAIL=$((FAIL+1))
    fi
  else
    green "Live generation test skipped (set LIVE_TEST=1 to enable)"
  fi
fi

# ---------- HuggingFace Inference API ----------
echo ""
echo "=== Testing HuggingFace Inference API (free tier) ==="
if [ -z "$HF_TOKEN" ]; then
  red "HF_TOKEN not set. Skipping."
  FAIL=$((FAIL+1))
else
  RESP=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $HF_TOKEN" \
    "https://huggingface.co/api/whoami-v2")
  HTTP=$(echo "$RESP" | tail -1)
  if [ "$HTTP" = "200" ]; then
    green "HuggingFace token OK (HTTP 200, authenticated)"
    PASS=$((PASS+1))
  else
    red "HuggingFace token FAILED (HTTP $HTTP)"
    FAIL=$((FAIL+1))
  fi
  # Live chat-completion test on a free model
  echo "-- Live chat test (mistralai/Mistral-7B-Instruct-v0.3)..."
  CRES=$(curl -s -w "\n%{http_code}" -X POST "https://api-inference.huggingface.co/v1/chat/completions" \
    -H "Authorization: Bearer $HF_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"model":"mistralai/Mistral-7B-Instruct-v0.3","messages":[{"role":"user","content":"Say OK in one word"}],"max_tokens":5}')
  HTTP2=$(echo "$CRES" | tail -1)
  BODY=$(echo "$CRES" | head -1)
  if [ "$HTTP2" = "200" ]; then
    green "HuggingFace live chat: OK (HTTP 200)"
    PASS=$((PASS+1))
  else
    echo "Chat test HTTP: $HTTP2"
    echo "$BODY" | head -2
    red "HuggingFace live chat: FAILED (model may be loading or rate-limited — token itself is valid if auth test passed)"
    FAIL=$((FAIL+1))
  fi
fi

echo ""
echo "=== Summary ==="
green "Passed: $PASS"; red "Failed: $FAIL"
[ "$FAIL" -eq 0 ] && green "ALL TESTS PASSED — keys are ready for deployment." || red "Fix failed keys before deploying."
