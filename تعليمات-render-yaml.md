# كيفية استخدام render.yaml في نشر celia.pro

## ما هو هذا الملف؟

`render.yaml` هو **تعريف خدمة Render بصيغة Blueprint** — بدلًا من تعبئة الحقول يدويًا في واجهة Render، يمكنك تمرير هذا الملف لـRender فيُنشئ الخدمة بكل إعداداتها تلقائيًا: أوامر البناء والتشغيل، المسار الصحي، والمتغيرات التسعة.

## ملاحظة مهمة: لا يحتوي أي سرّ

المتغيرات الحساسة (`DATABASE_URL`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `HF_TOKEN`) معرّفة بـ`sync: false` — أي أنها **مطلوبة منك عند الإنشاء ولا قيمة لها داخل الملف**. هذا يحافظ على القاعدة الذهبية: السرّ يُلصق في لوحة Render مباشرة، لا يمر عبر أي وسيط.

## الطريقتان لاستخدامه

### الطريقة 1 — الإرفاق أثناء إنشاء الخدمة (الموصى بها)

1. افتح [dashboard.render.com/blueprints/new](https://dashboard.render.com/blueprints/new) وسجّل الدخول
2. اختر مستودع `celia-pro-deployment`
3. في حقل **Blueprint File** اكتب: `render.yaml`
4. اضغط **Apply** — ينشئ Render الخدمة تلقائيًا بكل الإعدادات
5. سيُعرض لك نموذج إدخال قيم المتغيرات الأربعة `sync: false`:

| المتغير | القيمة |
|---------|--------|
| `DATABASE_URL` | السلسلة الكاملة من لوحة Neon (driver: Python asyncpg + Pooler — الصقها كما هي كاملة) |
| `GEMINI_API_KEY` | من [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| `GROQ_API_KEY` | من [console.groq.com/keys](https://console.groq.com/keys) |
| `HF_TOKEN` | من [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) — scope: Read |

6. اضغط **Apply** في نهاية النموذج — يبدأ البناء تلقائيًا وانتظر **Live**

### الطريقة 2 — يدويًا (إن أنشأت الخدمة سابقًا)

إذا أنشأت الخدمة يدويًا بالفعل كما كنا نفعل، فما يزال بإمكانك استخدام الملف كمرجع — الإعدادات الواردة فيه مطابقة تمامًا لما أرسلناه سابقًا، مع إضافتين:
- `healthCheckPath: /api/health` — يتيح لـRender مراقبة صحة الخدمة تلقائيًا
- `JWT_SECRET_KEY` مع `generateValue: true` — يولّده Render تلقائيًا عند الإنشاء عبر Blueprint

## تطابق الملف مع الكود الفعلي

| الإعداد | المصدر في الكود |
|---------|------------------|
| `buildCommand` | backend/requirements.txt موجود ✅ |
| `startCommand` | نقطة الدخول `api.main:app` مؤكدة بالاختبار ✅ |
| `/api/health` | endpoint موجود في api/main.py ✅ |
| `DB_POOL_SIZE=5` | database/connection.py:36 (default=10 — نحن نخفضه لحدود Neon) |
| `AUTH_REQUIRED=true` | api/main.py: قراءة `os.getenv("AUTH_REQUIRED", "true")` |
| `CORS_ORIGINS` | api/main.py + SecurityConfig |
| Groq fallback | core/llm_clients.py: GroqClient + LLMRouter (gemini → groq → hf) |

## قواعد مطلقة

1. لا تُلصق أي قيمة حساسة في المحادثة — أدخلها في نموذج Blueprint أو لوحة Render فقط
2. انسخ `DATABASE_URL` من لوحة Neon كاملة (بما فيها `sslmode=require`) — الكود معدّل ليتعامل معها
3. `AUTH_REQUIRED=true` من البداية — لا تغيّرها
4. بعد ظهور **Live** أخبرني فقط: «Render = Live»
