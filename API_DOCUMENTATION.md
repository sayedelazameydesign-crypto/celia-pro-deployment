# 📚 Celia.pro API Documentation

*Complete API reference for Celia.pro AI Agent System*

---

## 🌐 Base URL

```
Production: https://api.celia.pro/v1
Development: http://localhost:8000
```

---

## 🔐 Authentication

All protected endpoints require JWT authentication via Bearer token.

### Get Access Token

**Endpoint:** `POST /api/auth/login`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### Using the Token

Add the token to the `Authorization` header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

## 📡 Endpoints

### Health & Status

#### Health Check
```
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "3.2.0",
  "components": {
    "api": {"status": "healthy"},
    "tools": {"status": "healthy", "count": 5},
    "memory": {"status": "healthy"},
    "llm": {"status": "configured"},
    "rate_limiter": {"status": "healthy"},
    "database": {"status": "healthy"}
  },
  "timestamp": 1234567890.123
}
```

#### Readiness Check
```
GET /api/ready
```

**Response:**
```json
{
  "ready": true
}
```

#### Liveness Check
```
GET /api/live
```

**Response:**
```json
{
  "alive": true
}
```

---

### Chat

#### Send Message
```
POST /api/chat
```

**Authentication:** Required

**Request:**
```json
{
  "message": "Hello, how are you?",
  "conversation_id": "conv_123abc",  // Optional
  "provider": "gemini"  // Optional
}
```

**Response:**
```json
{
  "response": "I'm doing well, thank you!",
  "conversation_id": "conv_123abc",
  "steps": [
    {
      "id": "step_1",
      "description": "Process message",
      "status": "completed"
    }
  ],
  "tool_calls": [],
  "execution_time": 1.234
}
```

**Error Response:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Message cannot be empty",
    "details": {"field": "message"}
  }
}
```

---

### Conversations

#### Create Conversation
```
POST /api/conversations
```

**Authentication:** Required

**Request:**
```json
{
  "title": "My Conversation"
}
```

**Response:**
```json
{
  "conversation_id": "conv_123abc",
  "title": "My Conversation"
}
```

#### List Conversations
```
GET /api/conversations
```

**Authentication:** Required

**Response:**
```json
{
  "conversations": [
    {
      "id": "conv_123abc",
      "title": "My Conversation",
      "created_at": "2026-08-15T10:00:00Z",
      "updated_at": "2026-08-15T10:30:00Z",
      "message_count": 10
    }
  ]
}
```

#### Get Conversation History
```
GET /api/conversations/{conversation_id}/history
```

**Authentication:** Required

**Response:**
```json
{
  "messages": [
    {
      "id": "msg_1",
      "role": "user",
      "content": "Hello",
      "timestamp": "2026-08-15T10:00:00Z",
      "tool_calls": []
    },
    {
      "id": "msg_2",
      "role": "assistant",
      "content": "Hi there!",
      "timestamp": "2026-08-15T10:00:01Z",
      "tool_calls": []
    }
  ]
}
```

**Error Response:**
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Conversation not found",
    "details": {}
  }
}
```

---

### Tools

#### List Tools
```
GET /api/tools
```

**Authentication:** Not required

**Response:**
```json
{
  "tools": [
    {
      "name": "execute_code",
      "description": "Execute Python code safely",
      "category": "execution",
      "parameters": {
        "type": "object",
        "properties": {
          "code": {"type": "string"},
          "language": {"type": "string", "default": "python"}
        },
        "required": ["code"]
      },
      "risk_level": "medium"
    }
  ]
}
```

#### Execute Tool
```
POST /api/tools/{tool_name}/execute
```

**Authentication:** Required

**Request:**
```json
{
  "arguments": {
    "code": "print('Hello, World!')",
    "language": "python"
  }
}
```

**Response:**
```json
{
  "tool": "execute_code",
  "result": "Hello, World!\n"
}
```

**Error Response:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Code cannot be empty",
    "details": {"field": "code"}
  }
}
```

---

### Memory (Advanced)

#### Get Memory Summary
```
GET /api/memory
```

**Authentication:** Not required

**Response:**
```json
{
  "total_memories": 100,
  "categories": ["fact", "lesson", "preference"],
  "last_updated": "2026-08-15T10:00:00Z"
}
```

#### Store Memory
```
POST /api/memory/store
```

**Authentication:** Required

**Request:**
```json
{
  "key": "user_preference_food",
  "value": "Vegetarian",
  "type": "preference",
  "category": "food",
  "tags": ["diet", "preference"],
  "importance": 0.9,
  "ttl_seconds": 2592000,  // 30 days
  "generate_vector": true
}
```

**Response:**
```json
{
  "status": "stored",
  "memory_id": "mem_123abc",
  "key": "user_preference_food",
  "type": "preference",
  "has_vector": true,
  "expires_at": "2026-09-15T10:00:00Z"
}
```

#### Search Memories
```
GET /api/memory/search?query=food&limit=10&use_vector_search=true
```

**Authentication:** Required

**Query Parameters:**
- `query` (optional): Search query
- `key` (optional): Exact key match
- `category` (optional): Filter by category
- `tags` (optional): Filter by tags (comma-separated)
- `type` (optional): Filter by type
- `limit` (optional, default: 10): Number of results
- `use_vector_search` (optional, default: true): Enable semantic search

**Response:**
```json
{
  "results": [
    {
      "id": "mem_123abc",
      "key": "user_preference_food",
      "value": "Vegetarian",
      "type": "preference",
      "metadata": {
        "category": "food",
        "tags": ["diet", "preference"],
        "importance": 0.9
      },
      "score": 0.95,
      "search_method": "vector_similarity"
    }
  ],
  "count": 1,
  "search_strategy": "vector_similarity"
}
```

#### Get Memory by Key
```
GET /api/memory/{key}
```

**Authentication:** Required

**Response:**
```json
{
  "id": "mem_123abc",
  "key": "user_preference_food",
  "value": "Vegetarian",
  "type": "preference",
  "metadata": {
    "category": "food",
    "tags": ["diet", "preference"],
    "importance": 0.9
  },
  "state": {
    "access_count": 5,
    "last_accessed": "2026-08-15T10:00:00Z"
  },
  "expires_at": "2026-09-15T10:00:00Z",
  "created_at": "2026-08-15T10:00:00Z",
  "updated_at": "2026-08-15T10:00:00Z"
}
```

#### Delete Memory
```
DELETE /api/memory/{key}
```

**Authentication:** Required

**Response:**
```json
{
  "status": "deleted",
  "key": "user_preference_food"
}
```

#### Cleanup Expired Memories
```
POST /api/memory/cleanup
```

**Authentication:** Required

**Response:**
```json
{
  "status": "cleaned",
  "deleted_count": 10
}
```

---

### Reflection

#### Get Reflection Stats
```
GET /api/reflection/stats
```

**Authentication:** Not required

**Response:**
```json
{
  "total_reflections": 100,
  "by_type": {
    "pre_action": 40,
    "post_action": 50,
    "error_analysis": 10
  },
  "average_confidence": 0.85,
  "recent_reflections": [
    {
      "type": "post_action",
      "thought": "Action completed successfully",
      "confidence": 0.9,
      "timestamp": "2026-08-15T10:00:00Z"
    }
  ]
}
```

#### Get Reflection Memories
```
GET /api/reflection/memories
```

**Authentication:** Not required

**Response:**
```json
{
  "memories": [
    {
      "situation": "User asked for food recommendations",
      "action_taken": "Searched for restaurants",
      "outcome": "success",
      "lesson": "User prefers vegetarian restaurants",
      "confidence": 0.9,
      "usage_count": 5,
      "last_used": "2026-08-15T10:00:00Z",
      "created_at": "2026-08-10T10:00:00Z"
    }
  ]
}
```

---

### LLM Configuration

#### Configure LLM
```
POST /api/llm/configure
```

**Authentication:** Required

**Request:**
```json
{
  "gemini_api_key": "AIza...",
  "groq_api_key": "gsk_...",
  "hf_token": "hf_...",
  "primary_provider": "gemini",
  "gemini_model": "gemini-2.0-flash",
  "groq_model": "llama-3.3-70b-versatile",
  "hf_model": "meta-llama/Llama-3.3-70B-Instruct"
}
```

**Response:**
```json
{
  "status": "configured",
  "providers": {
    "gemini_configured": true,
    "groq_configured": true,
    "huggingface_configured": true
  }
}
```

**Error Response:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Gemini API key must start with 'AIza'",
    "details": {"field": "gemini_api_key"}
  }
}
```

#### Get LLM Status
```
GET /api/llm/status
```

**Authentication:** Not required

**Response:**
```json
{
  "configured": true,
  "primary": "gemini",
  "gemini_configured": true,
  "groq_configured": true,
  "huggingface_configured": true
}
```

#### Get LLM Providers
```
GET /api/llm/providers
```

**Authentication:** Not required

**Response:**
```json
{
  "providers": [
    {
      "id": "gemini",
      "name": "Google Gemini",
      "description": "Free tier - 15 requests/min, 1M tokens/min",
      "models": [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b"
      ],
      "requires": "GEMINI_API_KEY",
      "link": "https://aistudio.google.com/app/apikey"
    },
    {
      "id": "groq",
      "name": "Groq",
      "description": "Free tier - 30 requests/min, 1000 requests/day",
      "models": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
      ],
      "requires": "GROQ_API_KEY",
      "link": "https://console.groq.com/keys"
    },
    {
      "id": "huggingface",
      "name": "HuggingFace",
      "description": "Free tier - various open models",
      "models": [
        "meta-llama/Llama-3.3-70B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "google/gemma-2-2b-it",
        "HuggingFaceH4/zephyr-7b-beta"
      ],
      "requires": "HF_TOKEN",
      "link": "https://huggingface.co/settings/tokens"
    }
  ]
}
```

---

### System Metrics

#### Get System Metrics
```
GET /api/system/metrics
```

**Authentication:** Not required

**Response:**
```json
{
  "cost_tracking": {
    "total_requests": 1000,
    "total_input_tokens": 500000,
    "total_output_tokens": 250000,
    "total_tokens": 750000,
    "total_cost_usd": 0.0,
    "recent_requests": []
  },
  "tool_audit": {
    "total_executions": 500,
    "blocked": 5,
    "errors": 2,
    "recent": []
  },
  "rate_limiter": {
    "used": 50,
    "limit": 100,
    "window_seconds": 60,
    "remaining": 50
  }
}
```

---

## 🚨 Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "field_name",  // Optional
      "additional_info": "..."
    }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AUTHENTICATION_ERROR` | 401 | Authentication failed |
| `AUTHORIZATION_ERROR` | 403 | Not authorized |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 400 | Validation failed |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |
| `TOOL_EXECUTION_ERROR` | 500 | Tool execution failed |
| `DATABASE_ERROR` | 500 | Database operation failed |
| `LLM_PROVIDER_ERROR` | 503 | LLM provider error |
| `INTERNAL_ERROR` | 500 | Unexpected error |

---

## 🔐 Security Headers

All responses include security headers:

```
X-Request-ID: req_abc123
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
```

---

## 📊 Rate Limiting

Rate limits are applied per user:

- **Free tier:** 50 requests/minute
- **Pro tier:** 200 requests/minute
- **Business tier:** 1000 requests/minute

When rate limited, the response includes:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

---

## 🔗 WebSocket

### Connect to WebSocket

```
ws://localhost:8000/ws/{client_id}
```

### Message Types

#### Connected
```json
{
  "type": "connected",
  "client_id": "client_123",
  "message": "Welcome to celia.pro!"
}
```

#### Chat Message
```json
{
  "type": "chat",
  "content": "Hello!"
}
```

#### Processing
```json
{
  "type": "processing",
  "message": "Analyzing your request..."
}
```

#### Response
```json
{
  "type": "response",
  "content": "Hi there!",
  "conversation_id": "conv_123",
  "tool_calls": [],
  "execution_time": 1.234
}
```

#### Error
```json
{
  "type": "error",
  "message": "Error message"
}
```

#### Cancel
```json
{
  "type": "cancel"
}
```

#### Cancelled
```json
{
  "type": "cancelled",
  "message": "Processing cancelled"
}
```

---

## 📝 Examples

### Example 1: Chat with Authentication

```bash
# Login
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  | jq -r '.access_token')

# Send message
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello!"}'
```

### Example 2: Store and Retrieve Memory

```bash
# Store memory
curl -X POST http://localhost:8000/api/memory/store \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "preference_language",
    "value": "Arabic",
    "type": "preference",
    "category": "language"
  }'

# Search memory
curl -X GET "http://localhost:8000/api/memory/search?query=language" \
  -H "Authorization: Bearer $TOKEN"
```

### Example 3: Execute Tool

```bash
curl -X POST http://localhost:8000/api/tools/execute_code/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "code": "print(2 + 2)",
      "language": "python"
    }
  }'
```

---

## 🎯 Best Practices

1. **Always authenticate** requests to protected endpoints
2. **Handle errors** gracefully using the error codes
3. **Respect rate limits** to avoid being throttled
4. **Use WebSocket** for real-time communication
5. **Cache responses** when appropriate to reduce API calls
6. **Use semantic search** for better memory retrieval
7. **Set TTL** for temporary memories to save storage
8. **Monitor metrics** to track usage and performance

---

## 🔧 SDKs & Libraries

### Python SDK (Coming Soon)

```python
from celia import CeliaClient

client = CeliaClient(api_key="your_api_key")

# Chat
response = client.chat("Hello!")

# Memory
client.store_memory("key", "value", type="preference")
memories = client.search_memories("query")

# Tools
result = client.execute_tool("execute_code", {"code": "print(2+2)"})
```

### JavaScript SDK (Coming Soon)

```javascript
import { CeliaClient } from 'celia-pro';

const client = new CeliaClient({ apiKey: 'your_api_key' });

// Chat
const response = await client.chat('Hello!');

// Memory
await client.storeMemory('key', 'value', { type: 'preference' });
const memories = await client.searchMemories('query');

// Tools
const result = await client.executeTool('execute_code', { code: 'print(2+2)' });
```

---

## 📚 Additional Resources

- [GitHub Repository](https://github.com/celia-pro/celia)
- [Website](https://celia.pro)
- [Blog](https://celia.pro/blog)
- [Discord Community](https://discord.gg/celia-pro)
- [Twitter](https://twitter.com/celiapro)

---

## 📞 Support

- **Email:** support@celia.pro
- **Discord:** [Join our community](https://discord.gg/celia-pro)
- **GitHub Issues:** [Report bugs](https://github.com/celia-pro/celia/issues)

---

*Last Updated: 2026-08-15*  
*API Version: 1.0*
