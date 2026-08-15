# 🔥 Groq Smoke Test Guide

## الاختبارات اللي اتعملت

### ✅ التعديلات اللي تمت

1. **reasoning_effort parameter** - اتضاف في GroqClient
   - الافتراضي: `"low"` (بيقلل latency)
   - القيم المتاحة: `"low"`, `"medium"`, `"high"`

2. **GroqClient methods** - كلهم بيدعموا reasoning_effort
   - `chat()` - للمحادثات العادية
   - `chat_with_tools()` - للمحادثات مع function calling

3. **Smoke Tests** - اتعملت في `test_groq_integration.py`
   - 6 connectivity tests
   - 2 performance tests

---

## 🧪 إزاي تشغل الـ Smoke Tests

### الخطوة 1: احصل على Groq API Key

1. روح على: https://console.groq.com/keys
2. اعمل حساب (مجاني)
3. اضغط "Create API Key"
4. انسخ الـ key (هيبقى بالشكل: `gsk_...`)

### الخطوة 2: حط الـ API Key في Environment

```bash
# في Linux/Mac
export GROQ_API_KEY="gsk_your_key_here"

# في Windows (Command Prompt)
set GROQ_API_KEY=gsk_your_key_here

# في Windows (PowerShell)
$env:GROQ_API_KEY="gsk_your_key_here"
```

### الخطوة 3: شغل الـ Smoke Tests

```bash
cd /home/user/novamind/backend

# شغل كل الـ smoke tests
pytest tests/test_groq_integration.py -v -s

# أو شغل test واحد معين
pytest tests/test_groq_integration.py::TestGroqSmokeTest::test_groq_api_connectivity -v -s
```

### الخطوة 4: اتفرج على النتائج

لو كل حاجة شغالة، هتشوف حاجة زي كده:

```
✅ Groq API connectivity: ok
✅ openai/gpt-oss-120b: ok
✅ openai/gpt-oss-20b: ok
✅ Function calling works: test_tool
✅ reasoning_effort parameter works for all values
✅ LLMRouter with Groq fallback: ok
⚡ Response time: 0.45s
⚡ Latency comparison:
   reasoning_effort=low:  0.45s
   reasoning_effort=high: 1.23s
   📊 High is 2.7x slower
```

---

## 📊 الاختبارات المتاحة

### TestGroqSmokeTest (6 tests)

| Test | الوصف | إيه اللي بيختبره |
|------|-------|------------------|
| `test_groq_api_connectivity` | Basic connectivity | هل Groq API بترد؟ |
| `test_groq_model_openai_gpt_oss_120b` | Model 120b | هل الموديل ده شغال؟ |
| `test_groq_model_openai_gpt_oss_20b` | Model 20b | هل الموديل ده شغال؟ |
| `test_groq_function_calling` | Function calling | هل function calling شغال؟ |
| `test_groq_reasoning_effort_low` | reasoning_effort | هل الـ parameter ده شغال؟ |
| `test_groq_fallback_chain` | LLMRouter | هل الـ fallback chain شغال؟ |

### TestGroqLatency (2 tests)

| Test | الوصف | إيه اللي بيختبره |
|------|-------|------------------|
| `test_groq_response_time` | Response time | هل الـ response time معقول؟ |
| `test_groq_reasoning_effort_impact` | Latency impact | إيه تأثير reasoning_effort على latency؟ |

---

## 🎯 إزاي تعرف إن كل حاجة شغالة؟

### ✅ Success Indicators

1. **كل الـ 140 test عايزين** (من الاختبارات العادية)
2. **الـ 8 smoke tests اشتغلوا** (مش skip)
3. **مفيش errors** في الـ output
4. **Response time < 10s** لكل request

### ❌ Failure Indicators

1. **API Key error**: `GROQ_API_KEY environment variable not set`
   - الحل: حط الـ API key في environment

2. **Model not found**: `model_not_found`
   - الحل: تأكد إن الموديل متاح في Groq

3. **Rate limit exceeded**: `rate_limit_exceeded`
   - الحل: استنى شوية وبعدين حاول تاني

4. **Timeout**: `timeout`
   - الحل: جرب `reasoning_effort="low"`

---

## 🔧 Troubleshooting

### المشكلة: "GROQ_API_KEY not set"

```bash
# تأكد إن الـ key موجود
echo $GROQ_API_KEY

# لو فاضي، حطه تاني
export GROQ_API_KEY="gsk_your_key_here"
```

### المشكلة: "model_not_found"

```bash
# تأكد إن الموديل متاح
curl -H "Authorization: Bearer $GROQ_API_KEY" \
  https://api.groq.com/openai/v1/models | grep "gpt-oss"
```

### المشكلة: "rate_limit_exceeded"

- Groq free tier: 30 requests/minute
- استنى دقيقة وبعدين حاول تاني
- أو قلل عدد الـ tests اللي بتشمها

### المشكلة: "timeout" أو response بطيء

```python
# جرب reasoning_effort="low"
response = await client.chat(
    messages=messages,
    reasoning_effort="low"  # أسرع
)
```

---

## 📈 الأداء المتوقع

### OpenAI GPT OSS 20B
- Response time: 0.3-0.8s
- Reasoning effort impact: minimal
- Best for: Quick responses, tool calling

### OpenAI GPT OSS 120B
- Response time: 0.5-1.5s
- Reasoning effort impact: moderate
- Best for: Complex reasoning, agentic tasks

### reasoning_effort Impact

| Value | Latency | Use Case |
|-------|---------|----------|
| `low` | Fastest | Tool calling loops, simple tasks |
| `medium` | Moderate | Normal conversations |
| `high` | Slowest | Complex reasoning, math |

---

## ✅ Checklist

- [ ] حصلت على Groq API Key
- [ ] حطيت الـ key في environment
- [ ] شغلت الـ smoke tests
- [ ] كل الـ 6 smoke tests نجحوا
- [ ] Response time معقول (< 10s)
- [ ] Function calling شغال
- [ ] reasoning_effort parameter شغال
- [ ] LLMRouter fallback chain شغال

---

## 🚀 الخطوة الجاية

لو كل الـ smoke tests نجحت:

1. ✅ **Groq آمن للاستخدام** في production
2. ✅ **Fallback chain شغال** (Gemini → Groq → HuggingFace)
3. ✅ **reasoning_effort="low"** بيشتغل وبيقلل latency

الخطوة الجاية: **P1 - ChromaDB + Deployment Stack**

---

## 📞 الدعم

لو حصلت مشكلة:

1. تأكد إن الـ API key صحيح
2. تأكد إن الموديلات متاحة: https://console.groq.com/docs/models
3. تأكد إن مفيش rate limiting: https://console.groq.com/docs/rate-limits
4. شوف الـ logs: `pytest tests/test_groq_integration.py -v -s`

---

<div align="center">

**🔥 Groq Smoke Tests Ready**

*اختبر إن الموديلات شغالة فعلاً، مش بس على الورق*

</div>
