# 🎉 تم التحديث بنجاح! - NovaMind v1.1

## ✅ ما تم إضافته

### 🔷 دعم Google Gemini API (الخطة المجانية)
- ✅ Gemini 2.0 Flash (الأسرع)
- ✅ Gemini 2.0 Flash Lite
- ✅ Gemini 1.5 Flash
- ✅ Gemini 1.5 Flash 8B
- ✅ Function Calling متقدم
- ✅ 15 طلب/دقيقة، 1M tokens/دقيقة

### 🤗 دعم HuggingFace Inference API (الخطة المجانية)
- ✅ Llama 3.3 70B Instruct (الأقوى)
- ✅ Mistral 7B Instruct v0.3
- ✅ Gemma 2 2B IT
- ✅ Zephyr 7B Beta
- ✅ Tool Support عبر Prompt Engineering

### 🔄 LLM Router ذكي
- ✅ تبديل تلقائي بين المزودين
- ✅ Fallback عند فشل أحدهما
- ✅ واجهة موحدة
- ✅ معالجة أخطاء متقدمة

### 🎨 واجهة مستخدم محدثة
- ✅ نافذة إعداد API Keys
- ✅ اختيار المزود الأساسي
- ✅ اختيار النموذج
- ✅ عرض حالة الاتصال
- ✅ روابط مباشرة للحصول على المفاتيح

---

## 📁 الملفات الجديدة/المحدثة

### Backend
```
backend/
├── core/
│   └── llm_clients.py          ✨ جديد - Gemini & HuggingFace clients
├── api/
│   └── main.py                 🔄 محدث - endpoints جديدة
```

### Frontend
```
frontend/
└── src/
    └── App.tsx                 🔄 محدث - LLM Config Modal
```

---

## 🚀 كيفية الاستخدام

### 1. احصل على المفاتيح المجانية

#### 🔷 Gemini API Key
- الموقع: https://aistudio.google.com/app/apikey
- مجاني تماماً
- 15 طلب/دقيقة

#### 🤗 HuggingFace Token
- الموقع: https://huggingface.co/settings/tokens
- مجاني تماماً
- نماذج مفتوحة المصدر

### 2. شغّل النظام

```bash
# Terminal 1 - Backend
cd /home/user/novamind/backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd /home/user/novamind/frontend
npm run dev
```

### 3. افتح المتصفح
```
http://localhost:5173
```

### 4. إعداد المفاتيح

**من الواجهة:**
1. اضغط "إعداد API Keys" في الصفحة الرئيسية
2. أو اضغط ⚙️ في الشريط الجانبي
3. الصق المفاتيح
4. اختر المزود الأساسي
5. اضغط "حفظ وتفعيل"

**من API:**
```bash
curl -X POST http://localhost:8000/api/llm/configure \
  -H "Content-Type: application/json" \
  -d '{
    "gemini_api_key": "AIza...",
    "hf_token": "hf_...",
    "primary_provider": "gemini"
  }'
```

---

## 📡 Endpoints جديدة

### Configure LLM
```bash
POST /api/llm/configure
{
  "gemini_api_key": "AIza...",
  "hf_token": "hf_...",
  "primary_provider": "gemini",
  "gemini_model": "gemini-2.0-flash",
  "hf_model": "meta-llama/Llama-3.3-70B-Instruct"
}
```

### Get LLM Status
```bash
GET /api/llm/status
```

### List Providers
```bash
GET /api/llm/providers
```

---

## 🧪 اختبار النظام

### 1. تحقق من الصحة
```bash
curl http://localhost:8000/api/health
```

### 2. تحقق من حالة LLM
```bash
curl http://localhost:8000/api/llm/status
```

### 3. أرسل رسالة
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "مرحباً، كيف حالك؟"}'
```

---

## 🎯 الميزات

### التبديل التلقائي
- النظام يستخدم المزود الأساسي أولاً
- إذا فشل، ينتقل تلقائياً للمزود الثانوي
- لا تحتاج للتدخل اليدوي

### Function Calling
- Gemini: Function Calling أصلي
- HuggingFace: Tool Support عبر Prompt Engineering
- كلاهما يدعم استدعاء الأدوات

### معالجة الأخطاء
- إعادة المحاولة التلقائية
- رسائل خطأ واضحة
- Fallback ذكي

---

## 💡 نصائح

### أفضل إعداد
```json
{
  "gemini_api_key": "AIza...",
  "hf_token": "hf_...",
  "primary_provider": "gemini",
  "gemini_model": "gemini-2.0-flash",
  "hf_model": "meta-llama/Llama-3.3-70B-Instruct"
}
```

**لماذا؟**
- Gemini كأساسي: الأسرع والأكثر استقراراً
- HuggingFace كبديل: Llama 3.3 الأقوى
- كلاهما مفعّل: للتبديل التلقائي

### استخدام Gemini فقط
```json
{
  "gemini_api_key": "AIza...",
  "primary_provider": "gemini",
  "gemini_model": "gemini-2.0-flash"
}
```

### استخدام HuggingFace فقط
```json
{
  "hf_token": "hf_...",
  "primary_provider": "huggingface",
  "hf_model": "meta-llama/Llama-3.3-70B-Instruct"
}
```

---

## 📊 المقارنة

| المزود | السرعة | الحدود | النماذج | Function Calling |
|--------|--------|--------|---------|------------------|
| **Gemini** | ⭐⭐⭐⭐⭐ | 15 req/min | Gemini 2.0, 1.5 | ✅ ممتاز |
| **HuggingFace** | ⭐⭐⭐ | Rate limited | Llama, Mistral, Gemma | ⚠️ جيد |

---

## 🔍 حالة النظام الحالية

```bash
# Backend: ✅ يعمل على المنفذ 8000
curl http://localhost:8000/api/health

# Frontend: ✅ يعمل على المنفذ 5173
curl http://localhost:5173/

# LLM Status: ⚠️ غير مُعد (يحتاج مفاتيح)
curl http://localhost:8000/api/llm/status
```

---

## 📚 الوثائق

- 📖 [README.md](./README.md) - دليل شامل بالإنجليزية
- 🚀 [QUICK_START_AR.md](./QUICK_START_AR.md) - دليل البدء السريع بالعربية
- 🔑 [Gemini API Key](https://aistudio.google.com/app/apikey)
- 🔑 [HuggingFace Token](https://huggingface.co/settings/tokens)

---

## 🎓 أمثلة استخدام

### مثال 1: بحث ذكي
```
ابحث عن آخر تطورات GPT-5 واكتب ملخص بالعربية
```

### مثال 2: كتابة كود
```
Write a Python function to find prime numbers up to N
```

### مثال 3: تحليل
```
حلل مميزات وعيوب استخدام الذكاء الاصطناعي في الطب
```

### مثال 4: مشروع كامل
```
أنشئ مشروع Python لتحليل البيانات يتضمن:
- README بالعربية
- كود مع comments
- اختبارات
```

---

## ✅ Checklist

- [x] Backend يعمل
- [x] Frontend يعمل
- [x] Gemini Client مُنفذ
- [x] HuggingFace Client مُنفذ
- [x] LLM Router مُنفذ
- [x] واجهة إعداد المفاتيح
- [x] Endpoints جديدة
- [x] الوثائق محدثة
- [ ] إضافة مفاتيح API (يحتاج المستخدم)
- [ ] اختبار مع LLM حقيقي (يحتاج المستخدم)

---

<div align="center">

**🎉 النظام جاهز للاستخدام!**

*فقط أضف مفاتيح API المجانية من Google و HuggingFace*

*NovaMind v1.1 - Powered by Gemini & HuggingFace*

</div>
