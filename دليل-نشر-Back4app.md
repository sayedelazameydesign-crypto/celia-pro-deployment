# دليل نشر celia.pro على Back4app Containers

**الإصدار:** 1.0 — **التاريخ:** 15 أغسطس 2026 — **المؤلف:** Manus AI

هذا الدليل يوثق نشر خلفية celia.pro (FastAPI) على خطة Back4app Containers المجانية (Free tier). الخطة المجانية مُوثقة رسميًا بأنها **لا تتطلب بطاقة ائتمان** ("no credit card required") وتوفر 0.25 CPU مشتركة، 256 MB RAM، و100 GB نقل شهريًا [1] [2].

## لماذا Back4app مناسب لهذا المشروع

البنية الجاهزة لدينا تطابق متطلبات Back4app تمامًا: مستودع GitHub فيه `Dockerfile` في الجذر، وخلفية FastAPI لا تحمّل نماذج AI ثقيلة في الذاكرة عند التشغيل (نموذج `fastembed` يُحمَّل ببطء عند أول استخدام فعلي للذاكرة الدلالية فقط)، مما يجعل قيد 256 MB قابلًا للتحقق — وقد أُثبت تجريبيًا: الحاوية تعمل باستهلاك **~70 MB فقط عند التشغيل** (أقل بكثير من 256 MB).

## الخطوات (تُنفَّذ داخل لوحة back4app.com)

### الخطوة 1: إنشاء الحساب والخدمة

سجّل دخولك في [back4app.com](https://www.back4app.com) عبر GitHub، ثم من لوحة التحكم اختر **Containers** (أو Web Deployment حسب واجهة حسابك الجديدة) واضغط **Create App** أو **Connect GitHub**. عند تفويض المستودع، اختر `celia-pro-deployment` (private) — قد تحتاج تثبيت Back4app app على حساب GitHub أولًا.

### الخطوة 2: إعداد البناء

| الحقل | القيمة |
|-------|--------|
| Repository | `celia-pro-deployment` |
| Branch | `main` |
| Dockerfile path | `/Dockerfile` (الافتراضي — موجود في الجذر) |
| Custom build/deploy commands | اتركها فارغة (الـDockerfile يتولى كل شيء) |

### الخطوة 3: متغيرات البيئة (Environment Variables)

أضف المتغيرات التالية في لوحة Back4app → إعدادات الخدمة → Environment Variables (لا تُرسل أيًا منها في أي مكان آخر):

| المتغير | القيمة | المصدر |
|---------|--------|--------|
| `DATABASE_URL` | `postgresql+asyncpg://...` (Pooler connection string من لوحة Neon بعد التدوير) | neon.tech → Console |
| `JWT_SECRET_KEY` | قيمة 64 hex تُولَّد مرة واحدة فقط (`openssl rand -hex 32`) | تُولَّد محليًا عندك |
| `GEMINI_API_KEY` | مفتاح جديد | aistudio.google.com/app/apikey |
| `GROQ_API_KEY` | مفتاح جديد | console.groq.com/keys |
| `HF_TOKEN` | توكن جديد | huggingface.co/settings/tokens |
| `CORS_ORIGINS` | `https://cerulean-boba-48f59a.netlify.app` | رابط Netlify الحالي |
| `DB_POOL_SIZE` | **`2`** | حرج: لا تتجاوز 2 بسبب حد 256 MB |
| `DB_MAX_OVERFLOW` | `5` | ضبط إضافي للذاكرة |
| `AUTH_REQUIRED` | `true` | إلزامي قبل أي استخدام حقيقي |

**تحذير قيد الذاكرة:** القيمة الحاسمة هي `DB_POOL_SIZE=2` — أي قيمة أكبر قد تدفع الاستهلاك فوق 256 MB مع حمل متزامن.

### الخطوة 4: النشر

اضغط **Deploy**. أول بناء قد يستغرق 5-10 دقائق. بعد نجاحه ستحصل على Production URL بصيغة `https://celia-pro-deployment-xxxx.back4app.io` (أو مشابهة حسب اسم الخدمة).

## التحقق بعد النشر (يُنفَّذ تلقائيًا من Manus)

عند إرسال Production URL، سيُنفَّذ التسلسل التالي:

1. `curl https://URL/api/health` — التوقع: `{"status":"healthy","database":"healthy"}`
2. اختبار CORS من Netlify (preflight OPTIONS)
3. التسجيل + تسجيل الدخول + JWT
4. رسالة Agent حقيقية → إثبات persistence في Neon
5. قياس الذاكرة المتاحة عبر health/logs إذا أتيحت
6. إصدار Production Baseline v1 بصيغة PASS/FAIL/NOT EXECUTED

## خطة الطوارئ

إذا فشلت الخدمة بسبب نفاد الذاكرة (OOM): انتقل فورًا إلى Zeabur أو SnapDeploy (كلاهما موثق بلا فيزا في `خطة-النشر-المجانية-الموثقة-v3.0.md`) — نفس الـDockerfile ونفس المتغيرات، دون تغيير الكود.

## المراجع

[1]: https://www.back4app.com/pricing/container-as-a-service "Back4app Containers Pricing — Free plan: no credit card required"
[2]: https://www.back4app.com/containers "Back4app Containers — Deploy from GitHub, Run Dockers"
