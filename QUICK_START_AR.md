# 🚀 دليل الإعداد السريع - celia.pro

## الخطوة 1: الحصول على مفاتيح API المجانية

### 🔷 Gemini API Key (موصى به)

1. افتح: https://aistudio.google.com/app/apikey
2. سجل دخول بحساب Google
3. اضغط "Create API Key"
4. انسخ المفتاح (يبدأ بـ `AIza...`)

**المميزات:**
- ✅ 15 طلب/دقيقة
- ✅ 1M tokens/دقيقة  
- ✅ 1,500 طلب/يوم
- ✅ الأسرع والأحدث

### 🤗 HuggingFace Token (اختياري)

1. افتح: https://huggingface.co/settings/tokens
2. سجل دخول أو أنشئ حساب
3. اضغط "New token"
4. اختر "Read" permissions
5. انسخ الـ token (يبدأ بـ `hf_...`)

**المميزات:**
- ✅ نماذج مفتوحة المصدر
- ✅ Llama 3.3, Mistral, وغيرها
- ✅ بديل عند فشل Gemini

---

## الخطوة 2: تشغيل النظام

### تأكد من تشغيل الـ Backend و Frontend

```bash
# Terminal 1 - Backend
cd /home/user/novamind/backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd /home/user/novamind/frontend
npm run dev
```

---

## الخطوة 3: إعداد المفاتيح

### من الواجهة (الطريقة السهلة)

1. افتح المتصفح: http://localhost:5173
2. اضغط زر "إعداد API Keys" في الصفحة الرئيسية
3. أو اضغط أيقونة ⚙️ في الشريط الجانبي

4. في نافذة الإعداد:
   - 🔷 الصق Gemini API Key
   - 🤗 الصق HuggingFace Token (اختياري)
   - اختر المزود الأساسي (Gemini موصى به)
   - اختر النموذج المناسب

5. اضغط "حفظ وتفعيل"

### من API (للمطورين)

```bash
curl -X POST http://localhost:8000/api/llm/configure \
  -H "Content-Type: application/json" \
  -d '{
    "gemini_api_key": "AIza...",
    "hf_token": "hf_...",
    "primary_provider": "gemini",
    "gemini_model": "gemini-2.0-flash",
    "hf_model": "meta-llama/Llama-3.3-70B-Instruct"
  }'
```

---

## الخطوة 4: ابدأ الاستخدام!

### جرب هذه الأمثلة:

#### 🔍 البحث على الويب
```
ابحث عن آخر تطورات الذكاء الاصطناعي في 2026
```

#### 💻 كتابة الكود
```
Write a Python script to analyze CSV data and calculate statistics
```

#### 📁 إدارة الملفات
```
أنشئ ملف README يحتوي على معلومات المشروع
```

#### 🖥️ أوامر النظام
```
Check system information and disk usage
```

#### 🧠 التحليل العميق
```
حلل مميزات وعيوب استخدام الذكاء الاصطناعي في التعليم
```

---

## ✅ التحقق من الإعداد

### تأكد من عمل النظام:

```bash
# Check health
curl http://localhost:8000/api/health

# Check LLM status
curl http://localhost:8000/api/llm/status
```

يجب أن ترى:
```json
{
  "status": "healthy",
  "agent": {
    "llm": {
      "gemini_configured": true,
      "huggingface_configured": true,
      "primary": "gemini"
    }
  }
}
```

---

## 🎯 نصائح مهمة

### 1. استخدم Gemini كـ Primary
- أسرع وأكثر استقراراً
- حدود أعلى في الخطة المجانية

### 2. فعّل كلا المزودين
- النظام ينتقل تلقائياً عند فشل أحدهما
- احتياطي ممتاز

### 3. اختر النموذج المناسب
- `gemini-2.0-flash` - الأسرع (موصى به)
- `gemini-1.5-flash` - متوازن
- `Llama-3.3-70B` - الأقوى من HuggingFace

### 4. راقب الاستخدام
- Gemini: 15 طلب/دقيقة
- HuggingFace: rate limited
- النظام يتعامل مع الحدود تلقائياً

---

## 🐛 حل المشاكل

### "API Error" أو "401 Unauthorized"
- ✅ تأكد من صحة المفتاح/الرمز
- ✅ تأكد من نسخه بالكامل
- ✅ أعد إنشاء المفتاح إذا لزم الأمر

### "Rate limit exceeded"
- ⏳ انتظر دقيقة وحاول مرة أخرى
- 🔄 النظام ينتقل تلقائياً للمزود الآخر
- 📊 قلل عدد الطلبات

### "Model is loading" (HuggingFace)
- ⏳ انتظر 30-60 ثانية
- 🔄 النموذج يحمّل لأول مرة
- ✅ بعد التحميل سيكون أسرع

### لا توجد استجابة
- 🔍 تأكد من تشغيل Backend و Frontend
- 🌐 تحقق من اتصال الإنترنت
- 🔑 تأكد من صحة المفاتيح

---

## 📊 المقارنة بين المزودين

| الميزة | Gemini | HuggingFace |
|--------|--------|-------------|
| **السعر** | مجاني | مجاني |
| **السرعة** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **الحدود** | 15 req/min | Rate limited |
| **النماذج** | Gemini 2.0, 1.5 | Llama, Mistral, Gemma |
| **Function Calling** | ✅ ممتاز | ⚠️ محدود |
| **الاستقرار** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## 🎓 أمثلة متقدمة

### مثال 1: بحث وتحليل
```
ابحث عن أحدث أبحاث الذكاء الاصطناعي في الطب، 
ثم حلل النتائج واكتب ملخص بالعربية
```

### مثال 2: كتابة كود
```
Write a Python script that:
1. Reads a CSV file
2. Calculates statistics
3. Creates a chart
4. Saves the results
```

### مثال 3: مشروع كامل
```
أنشئ مشروع Python كامل يتضمن:
- ملف README بالعربية
- كود Python مع comments
- اختبارات unit tests
- ملف requirements.txt
```

---

## 📞 المساعدة

### روابط مفيدة:
- 📖 [celia.pro Docs](./README.md)
- 📖 [Gemini API Docs](https://ai.google.dev/docs)
- 🤗 [HuggingFace Docs](https://huggingface.co/docs)
- 🔑 [Gemini API Key](https://aistudio.google.com/app/apikey)
- 🔑 [HuggingFace Tokens](https://huggingface.co/settings/tokens)

---

<div align="center">

**🎉 أنت جاهز للاستخدام!**

*celia.pro - مدعوم بـ Gemini & HuggingFace*

</div>
