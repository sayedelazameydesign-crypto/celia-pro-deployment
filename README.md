# 🧠 celia.pro - Advanced AI Agent System 2026

<div align="center">

![celia.pro](https://img.shields.io/badge/celia.pro-v2.0.0-cyan)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![React](https://img.shields.io/badge/React-19-61dafb)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-009688)
![Gemini](https://img.shields.io/badge/Gemini-Free%20Tier-blue)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Free%20Tier-yellow)
![Tests](https://img.shields.io/badge/Tests-93%20passing-brightgreen)
![License](https://img.shields.io/badge/License-Proprietary-red)

**نظام وكيل ذكاء اصطناعي متقدم متعدد الأدوات**

*مدعوم بـ Gemini & HuggingFace - الخطة المجانية*

*© 2026 celia.pro - جميع الحقوق محفوظة*

</div>

---

## ⚠️ تحذير قانوني صريح / EXPLICIT LEGAL WARNING

> **🚫 هذا البرنامج محمي بترخيص خاص صارم**
> 
> **أي استخدام دون إذن صريح مسبق من celia.pro ممنوع تماماً**
> 
> هذا البرنامج ملكية حصرية لـ celia.pro ومحمي بموجب قوانين الملكية الفكرية الدولية.
> 
> **محظور تماماً:**
> - ❌ استخدام البرنامج لأي غرض
> - ❌ النسخ أو التوزيع
> - ❌ التعديل أو إنشاء أعمال مشتقة
> - ❌ الهندسة العكسية
> - ❌ النشر على أي خادم
> - ❌ الدمج في منتجات أخرى
> 
> **العواقب القانونية:**
> - ⚖️ دعوى مدنية للتعويضات
> - ⚖️ ملاحقة جنائية
> - ⚖️ أوامر قضائية بوقف الاستخدام
> - ⚖️ تعويضات مالية تصل للحد الأقصى
> 
> **للاستفسار عن الترخيص:**
> 📧 licensing@celia.pro
> 🌐 https://celia.pro

---

## 🌟 نظرة عامة

**celia.pro** هو نظام وكيل ذكاء اصطناعي متكامل مصمم لمنافسة أنظمة مثل Claude و Manus في عام 2026. يتميز بدعم مزودي ذكاء اصطناعي مجانيين:

- 🔷 **Google Gemini** - 15 طلب/دقيقة، 1M tokens/دقيقة (مجاني)
- 🤗 **HuggingFace** - نماذج مفتوحة المصدر مثل Llama 3.3, Mistral (مجاني)

### القدرات الأساسية:

- 🔍 **البحث على الويب** - البحث عن معلومات حديثة
- 💻 **تنفيذ الكود** - تشغيل Python/JavaScript/Bash
- 📁 **إدارة الملفات** - قراءة/كتابة/تنظيم الملفات
- 🖥️ **أوامر Shell** - تنفيذ أوامر النظام
- 🧠 **التفكير العميق** - التحليل والتخطيط المنطقي

## 🚀 التشغيل السريع

### المتطلبات
- Python 3.11+
- Node.js 20+
- npm 10+

### 1. تثبيت الـ Backend
```bash
cd backend
pip install -r requirements.txt
```

### 2. تشغيل الـ Backend
```bash
cd backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. تثبيت الـ Frontend
```bash
cd frontend
npm install
```

### 4. تشغيل الـ Frontend
```bash
cd frontend
npm run dev
```

### 5. فتح المتصفح
```
http://localhost:5173
```

## 🔑 إعداد مفاتيح API

### 🔷 Google Gemini API (مجاني)

1. اذهب إلى [Google AI Studio](https://aistudio.google.com/app/apikey)
2. سجل دخول بحساب Google
3. اضغط "Create API Key"
4. انسخ المفتاح (يبدأ بـ `AIza...`)

**الحدود المجانية:**
- 15 طلب/دقيقة
- 1,000,000 tokens/دقيقة
- 1,500 طلب/يوم

**النماذج المتاحة:**
- `gemini-2.0-flash` - الأسرع والأحدث
- `gemini-2.0-flash-lite` - أخف وأسرع
- `gemini-1.5-flash` - متوازن
- `gemini-1.5-flash-8b` - أصغر حجماً

### 🤗 HuggingFace Token (مجاني)

1. اذهب إلى [HuggingFace Settings](https://huggingface.co/settings/tokens)
2. سجل دخول أو أنشئ حساب
3. اضغط "New token"
4. اختر "Read" permissions
5. انسخ الـ token (يبدأ بـ `hf_...`)

**الحدود المجانية:**
- Rate limited حسب النموذج
- وصول لمعظم النماذج المفتوحة

**النماذج المتاحة:**
- `meta-llama/Llama-3.3-70B-Instruct` - الأقوى
- `mistralai/Mistral-7B-Instruct-v0.3` - متوازن
- `google/gemma-2-2b-it` - خفيف
- `HuggingFaceH4/zephyr-7b-beta` - سريع

### إعداد من الواجهة

1. افتح `http://localhost:5173`
2. اضغط على "إعداد API Keys" أو أيقونة الإعدادات في الشريط الجانبي
3. أدخل المفتاح/الرمز المناسب
4. اختر المزود الأساسي
5. اضغط "حفظ وتفعيل"

### إعداد عبر API

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

## 🏗️ البنية المعمارية

```
┌─────────────────────────────────────────────────────────┐
│                    celia.pro System                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │   Frontend   │◄──►│   REST API   │◄──►│   Agent    │ │
│  │  React + TS  │    │   FastAPI    │    │   Core     │ │
│  └─────────────┘    └──────────────┘    └─────┬──────┘ │
│                                                 │        │
│  ┌──────────────────────────────────────────────┤       │
│  │              LLM Router Layer                 │       │
│  │  ┌─────────────────┐  ┌──────────────────┐  │       │
│  │  │  Gemini Client  │  │  HuggingFace     │  │       │
│  │  │  (Free Tier)    │  │  Client          │  │       │
│  │  └─────────────────┘  └──────────────────┘  │       │
│  └──────────────────────────────────────────────┘       │
│                                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │                   Tools Layer                 │       │
│  ├──────────┬──────────┬──────────┬─────────────┤       │
│  │  Web     │  Code    │  File    │   Shell     │       │
│  │  Search  │  Executor│  Manager │   Tool      │       │
│  └──────────┴──────────┴──────────┴─────────────┘       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Memory System                        │   │
│  │  ┌────────────────┐  ┌──────────────────────┐   │   │
│  │  │  Short-term    │  │  Long-term           │   │   │
│  │  │  (Context)     │  │  (Persistent)        │   │   │
│  │  └────────────────┘  └──────────────────────┘   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Task Planner                         │   │
│  │  • Decomposition  • Ordering  • Replanning       │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 📡 API Endpoints

### LLM Configuration
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/llm/configure` | Configure LLM providers |
| GET | `/api/llm/status` | Get current LLM status |
| GET | `/api/llm/providers` | List available providers |

### REST API
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | System info |
| GET | `/api/health` | Health check |
| POST | `/api/chat` | Send message |
| POST | `/api/conversations` | Create conversation |
| GET | `/api/conversations` | List conversations |
| GET | `/api/conversations/{id}/history` | Get history |
| GET | `/api/tools` | List tools |
| POST | `/api/tools/{name}/execute` | Execute tool |
| GET | `/api/memory` | Memory summary |
| POST | `/api/memory/store` | Store memory |
| GET | `/api/memory/search` | Search memory |
| POST | `/api/config` | Update config |

### WebSocket
```
ws://localhost:8000/ws/{client_id}
```

## 🔧 الأدوات المتاحة

### 🔍 Web Search
```python
tool: "web_search"
args: {"query": "AI news 2026", "num_results": 5, "search_type": "general"}
```

### 💻 Code Execution
```python
tool: "execute_code"
args: {"code": "print('Hello World')", "language": "python", "timeout": 30}
```

### 📁 File Manager
```python
tool: "file_manager"
args: {"action": "read|write|list|mkdir|delete|info|search", "path": "./file.txt"}
```

### 🖥️ Shell
```python
tool: "shell"
args: {"command": "ls -la", "cwd": "/home/user", "timeout": 30}
```

### 🧠 Thinking
```python
tool: "think"
args: {"thought": "Let me analyze this step by step...", "type": "reasoning"}
```

## 🤖 LLM Router

النظام يستخدم LLM Router ذكي للتبديل التلقائي بين المزودين:

```python
from core.llm_clients import LLMRouter

router = LLMRouter(
    gemini_key="AIza...",
    hf_token="hf_...",
    primary="gemini",
    gemini_model="gemini-2.0-flash",
    hf_model="meta-llama/Llama-3.3-70B-Instruct"
)

# سيستخدم Gemini أولاً، وإذا فشل ينتقل لـ HuggingFace تلقائياً
response = await router.chat_with_tools(messages, tools)
```

### الميزات:
- ✅ تبديل تلقائي عند فشل مزود
- ✅ دعم Function Calling
- ✅ توحيد الواجهة بين المزودين
- ✅ معالجة الأخطاء وإعادة المحاولة

## 🧪 أمثلة الاستخدام

### من خلال الواجهة
1. افتح `http://localhost:5173`
2. اضغط "إعداد API Keys"
3. أدخل Gemini API Key أو HuggingFace Token
4. اكتب رسالتك في حقل الإدخال
5. شاهد النظام وهو يخطط وينفذ

### من خلال API
```bash
#Configure LLM
curl -X POST http://localhost:8000/api/llm/configure \
  -H "Content-Type: application/json" \
  -d '{"gemini_api_key": "AIza..."}'

# Send message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "ابحث عن آخر أخبار الذكاء الاصطناعي"}'
```

### من خلال Python
```python
import httpx

# Configure
httpx.post("http://localhost:8000/api/llm/configure", json={
    "gemini_api_key": "AIza...",
    "primary_provider": "gemini"
})

# Chat
response = httpx.post("http://localhost:8000/api/chat", json={
    "message": "Write a Python script to sort a list"
})
print(response.json()["response"])
```

## 🔌 إضافة أدوات جديدة

```python
from tools.base import BaseTool

class MyCustomTool(BaseTool):
    name = "my_tool"
    description = "وصف الأداة"
    category = "custom"
    parameters = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input data"}
        },
        "required": ["input"]
    }

    async def execute(self, input: str, **kwargs) -> str:
        return f"Result: {input}"
```

ثم سجلها:
```python
agent.tool_registry.register(MyCustomTool())
```

## 📁 هيكل المشروع

```
celia-pro/
├── backend/
│   ├── api/
│   │   └── main.py          # FastAPI application
│   ├── core/
│   │   ├── agent.py         # Agent orchestration
│   │   ├── planner.py       # Task planning
│   │   ├── memory.py        # Memory system
│   │   └── llm_clients.py   # LLM providers
│   ├── models/
│   │   └── schemas.py       # Data models
│   ├── tools/
│   │   ├── base.py          # Tool registry
│   │   ├── web_search.py    # Web search
│   │   ├── code_executor.py # Code execution
│   │   ├── file_manager.py  # File management
│   │   ├── shell.py         # Shell commands
│   │   └── thinking.py      # Reasoning tool
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Main application
│   │   ├── index.css        # Styles
│   │   └── main.tsx         # Entry point
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 💡 نصائح الاستخدام

### للحصول على أفضل أداء:
1. **استخدم Gemini كـ primary** - أسرع وأكثر استقراراً
2. **فعّل كلا المزودين** - للتبديل التلقائي عند الفشل
3. **اختر النموذج المناسب** - Gemini 2.0 Flash للأسرع، Llama 3.3 للأقوى
4. **راقب الاستخدام** - الخطة المجانية لها حدود

### حل المشاكل الشائعة:
- **Gemini Rate Limit**: انتظر دقيقة أو بدّل لـ HuggingFace
- **HuggingFace Model Loading**: انتظر حتى يحمّل النموذج (قد يستغرق دقيقة)
- **لا توجد استجابة**: تأكد من صحة المفاتيح واتصال الإنترنت

## 🎯 المميزات المستقبلية

- [ ] دعم المزيد من مزودي LLM (OpenRouter, Together AI)
- [ ] نظام وكلاء متعددين (Multi-Agent)
- [ ] واجهة سحب وإفلات لبناء سير العمل
- [ ] نظام مصادقة ومستخدمين
- [ ] قاعدة بيانات للمحادثات
- [ ] دعم الصور والملفات المتعددة
- [ ] وضع التعاون الجماعي
- [ ] نظام إضافات (Plugins)
- [ ] Caching ذكي لتقليل الاستخدام

## 📄 الترخيص

© 2026 celia.pro - جميع الحقوق محفوظة. هذا البرنامج ملكية خاصة. انظر ملف [LICENSE](./LICENSE) للتفاصيل.

---

<div align="center">

**صُنع بـ ❤️ لنظام ذكاء اصطناعي عربي متقدم**

*celia.pro - Powered by Gemini & HuggingFace*

*© 2026 celia.pro*

</div>
