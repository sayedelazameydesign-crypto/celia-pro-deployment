# التحقق الرسمي من أسعار المنصات — 15 أغسطس 2026

المصادر الرسمية مباشرة (تم الاستخراج اليوم، max_age=600s):

## Zeabur Free Plan (https://zeabur.com/docs/en-US/pricing/free-plan — محدث 22 يونيو 2026)
- "No credit card required — just sign up and start deploying." ✅ مؤكد رسمي
- Auto-sleep بعد الخمول + cold start لثوانٍ (لا scale-to-zero حرفيًا بل auto-sleep)
- لا SLA، لا email، لا backup/log forwarding آلي (منذ Dev Plan)
- Dev Plan = $5/شهر (تجربة 14 يوم)

## Koyeb Pricing FAQ (https://www.koyeb.com/docs/faqs/pricing)
- **⚠️ تصحيح مهم:** Koyeb FAQ الرسمية: "We require a credit card to prevent fraud and abuse." — تضع hold بـ$29 عند إدخال البطاقة، وتبدأ الفوترة pay-per-use.
- free tier: خدمة web واحدة `free` (Frankfurt/Washington DC، 512MB RAM، 0.1 vCPU، 2GB SSD) + قاعدة PostgreSQL مجانية محدودة (5 ساعات نشاط + 1GB) — لكن **التسجيل على Koyeb نفسه يتطلب بطاقة** وفق FAQ الرسمية.
- Scale-to-Zero غير متاحة بعد (on public roadmap) — الخدمات المجانية free instance وليست scale-to-zero بالمعنى الفني.
- 100GB outbound bandwidth مجاني، بعدها $0.04/GB.
- **الاستنتاج:** Koyeb لم يعد خيارًا "بلا فيزا"؛ العبارة السابقة "قد يطلبون فيزا فقط إذا فشل التحقق" كانت مبنية على مصدر أقل رسمية. المصدر الرسمي الحالي يقول: البطاقة مطلوبة.

## Neon (https://neon.com/pricing)
- Free: $0/month دائم، "no credit card required" ✅ مؤكد
- 100 CU-hours/project شهريًا + 0.5GB تخزين/مشروع + 5GB egress
- Scale-to-zero بعد 5 دقائق (compute = $0 أثناء التعليق) ✅
- 10 مشاريع، 10 branches، autoscaling حتى 2 CU (8GB RAM)
- تجاوز أي حد → تعليق compute حتى الشهر التالي
- pgvector وpooler مشمولان في كل الخطط ✅
- History window 6 ساعات (1GB)؛ snapshots: يدوي 1 فقط، مجدول لا يوجد في Free
- Monitoring retention يوم واحد، لا spending notifications في Free

## Netlify (https://www.netlify.com/pricing/)
- Free "$0 forever" لفردي ✅، بدون فيزا (Git sign-in)
- **تصحيح مهم:** Netlify انتقلت لنموذج Credits (وليس GB النقلي القديم):
  - Free = 300 credits/شهر؛ bandwidth = 20 credits/GB؛ production deploy = 15 credits؛ web requests = 2 credits لكل 10 آلاف
  - Personal = $9/شهر (1000 credits)، Pro = $20/شهر
  - Custom domains مع SSL متاحة في Free ✅؛ Functions/AI models/Blob مذكورة في Free
- HTTPS ✅، CDN عالمي ✅، firewall basic ✅ في Free

## خلاصة المنهجية
1. **الخيارات المؤكدة بلا فيزا (رسميًا):** Neon + Netlify + Zeabur.
2. **Koyeb:** يتطلب بطاقة وفق FAQ الرسمية — يُستبعد من خطة "بلا فيزا" نهائيًا، أو يُستخدم فقط إذا كان لدى المستخدم بطاقة ويريد free instance.
3. العبارة "scale-to-zero لكل المنصات" صحيحة فقط لـNeon؛ Zeabur وKoyeb يستخدمان auto-sleep.
4. كل الحدود قابلة للتغير — توثيق التاريخ (15 أغسطس 2026) إلزامي.
