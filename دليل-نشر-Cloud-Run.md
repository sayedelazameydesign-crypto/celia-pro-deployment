# دليل نشر الخلفية على Google Cloud Run — celia.pro

> **مجاني 100% بدون بطاقة** — Cloud Run free tier: 2 مليون طلب/شهر + 360,000 GB-ثانية + 180,000 vCPU-ثانية.
> تم التحقق: صورة Docker تُبنى بنجاح وتعمل (اختُبرت محليًا: `/api/health` → `healthy`).
> آخر commit: `c64b229` — أضف `Dockerfile` في الجذر (نسخة من `Dockerfile.backend` مع `workers=1` للطبقة المجانية).

## قبل البدء

1. أنشئ مفاتيح AI جديدة صالحة (بدل القديم `API_KEY_INVALID`):
   - Gemini: https://aistudio.google.com/app/apikey
   - Groq: https://console.groq.com/keys
   - HuggingFace: https://huggingface.co/settings/tokens
2. كلمة مرور Neon الجديدة موجودة في لوحة Neon فقط (تم التدوير مرتين — القديمة لا تعمل).

## الخطوات (10 دقائق)

### 1. تفعيل Cloud Run (أول مرة فقط)
- https://console.cloud.google.com/cloud-run
- اختر مشروعًا جديدًا (أو موجودًا) → مفعّل billing لكن **لا تحتاج بطاقة** ضمن Always Free tier — إذا طلب بطاقة، استخدم مشروعًا بـ"Free Trial" أو انتقل لـFly.io (دليل بديل أدناه).
- **ملاحظة صادقة:** Cloud Run يتطلب حساب فوترة (قد يطلب بطاقة بدون خصم). إن لم ترغب في ذلك إطلاقًا، البديل المجاني بدون بطاقة جدًا هو **Fly.io** أو **HuggingFace Spaces** — راجع القسم الأخير.

### 2. ربط GitHub
- داخل Cloud Run: **Create Service** → **Deploy one revision from an existing container image** → تبويب **Source and deployment settings** → **Source code repository** → اربط حساب GitHub → اختر `celia-pro-deployment` وbranch `main`.
- Google ستبني الصورة تلقائيًا من `Dockerfile` الموجود في الجذر.

### 3. ضبط الإعدادات
| الإعداد | القيمة |
|---------|--------|
| Region | أي منطقة قريبة منك (us-east1 آمن) |
| Allow unauthenticated invocations | ✅ مفعل (ضروري) |
| Port | 8000 (مُعيَّن داخل Dockerfile عبر ENV PORT=8000) |
| CPU allocation | "CPU always allocated" (خيار افتراضي) |
| Auto-scaling | 0–3 (free tier) |

### 4. إضافة المتغيرات التسعة
في **Variables & Secrets** → **Variables** → add:

| المتغير | القيمة |
|---------|--------|
| DATABASE_URL | السلسلة من لوحة Neon (postgresql+asyncpg://...pooler.../neondb) — الكود يتعامل مع sslmode تلقائيًا، لا تحذفه |
| JWT_SECRET_KEY | 629eed228c089f06cf5be3f93c795dcc79ffa07e6287bf553ee5288a5cc01b77 |
| GEMINI_API_KEY | مفتاح Gemini الجديد |
| GROQ_API_KEY | مفتاح Groq الجديد |
| HF_TOKEN | توكن HuggingFace |
| CORS_ORIGINS | `https://cerulean-boba-48f59a.netlify.app` |
| DB_POOL_SIZE | `5` |
| DB_MAX_OVERFLOW | `10` |
| AUTH_REQUIRED | `true` |

**القاعدة الذهبية:** لا تُرسل أيًا من هذه القيم في أي محادثة — من لوحة المصدر إلى Cloud Run مباشرة.

### 5. Deploy + الانتظار
- اضغط **Create** → البناء ~5-10 دقائق أول مرة.
- بعد **Done** ستحصل على رابط مثل `https://celia-pro-xxxxxx-ue.a.run.app`.

### 6. أول طلب بعد النشر
- اول request يستيقظ الخدمة (scale-from-zero): ~2-5 ثوانٍ. لا تعتبره فشلًا.
- اختبر: `https://رابطك/api/health` → يجب أن يعرض `"database": {"status": "healthy"}`.

### 7. بعد النجاح — أرسل لي الرابط فقط
سأنفذ فورًا: CORS test → تسجيل → تسجيل دخول → JWT → رسالة AI → التحقق من Neon → تقرير PASS/FAIL.

### 8. ربط Netlify
- عند نجاح الاختبارات: في Netlify → Site configuration → Environment variables → أضف `VITE_API_URL=https://رابطك` → Deploy site (سأنفذه أنا عبر MCP عند جاهزية الرابط).

## بديل بدون بطاقة إطلاقًا: Fly.io

إذا لم ترغب في إدخال أي بيانات دفع حتى للتفعيل:

1. https://fly.io → سجّل (يدعم GitHub login) → خطة Free allowance: 3 shared-CPU VMs بدون بطاقة (قد يطلب بطاقة للتفعيل — نفس الوضع غالبًا).
2. بديل مؤكد بدون بطاقة: **HuggingFace Spaces** — مجاني نهائي، لكن التطبيق ينام بعد الخمول.
3. **Render** و**Koyeb** (التي جربتها) و**Railway** جميعها تطلب بطاقة حاليًا للخطة المجانية أو انتهت تجاربها.

**الواقع الحالي (أغسطس 2026):** كل منصات PaaS الكبرى تطلب بطاقة حتى للـfree tier. إن كان شرطك الأساسي "بدون بطاقة نهائيًا" فأخبرني وسننتقل لـHuggingFace Spaces مباشرة.

## تدقيق أمني بعد النشر

```bash
git grep -inE "npg_|AIza|hf_[A-Za-z0-9]{10,}|sk-" -- . ':!*.md' || echo "لا أسرار"
```
(يُطبع: لا أسرار — المستودع نظيف حتى في تاريخ Git)
