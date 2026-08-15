"""
celia.pro LLM Clients
======================
Multi-provider LLM client supporting Gemini (free tier), Groq (free tier), and HuggingFace.
"""

import aiohttp
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Google Gemini API client (free tier).
    - Gemini 2.0 Flash: 15 requests/min, 1M tokens/min
    - Gemini 1.5 Flash: 15 requests/min, 1M tokens/min
    - Supports function calling (tools)
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    SUPPORTED_MODELS = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
    ]

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _convert_tools_to_gemini(self, tools: List[Dict]) -> List[Dict]:
        """Convert OpenAI-format tools to Gemini format."""
        if not tools:
            return []

        functions = []
        for tool in tools:
            func = tool.get("function", {})
            functions.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {"type": "object", "properties": {}})
            })

        return [{"functionDeclarations": functions}]

    def _convert_messages_to_gemini(self, messages: List[Dict]) -> tuple:
        """Convert messages to Gemini format."""
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                system_instruction = {"parts": {"text": content}}
            elif role == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
            elif role == "assistant":
                parts = []
                if content:
                    parts.append({"text": content})

                # Handle tool calls
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        func = tc.get("function", {})
                        parts.append({
                            "functionCall": {
                                "name": func.get("name", ""),
                                "args": json.loads(func.get("arguments", "{}"))
                            }
                        })

                if parts:
                    contents.append({
                        "role": "model",
                        "parts": parts
                    })
            elif role == "tool":
                contents.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.get("name", "unknown"),
                            "response": {"result": content}
                        }
                    }]
                })

        return system_instruction, contents

    async def chat(self, messages: List[Dict], temperature: float = 0.7,
                   max_tokens: int = 4096, **kwargs) -> Dict:
        """Simple chat without tools."""
        system_instruction, contents = self._convert_messages_to_gemini(messages)

        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        if system_instruction:
            body["systemInstruction"] = system_instruction

        session = await self._get_session()
        async with session.post(url, json=body) as resp:
            data = await resp.json()
            if "error" in data:
                raise Exception(f"Gemini API error: {data['error']['message']}")

            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = " ".join(p.get("text", "") for p in parts if "text" in p)
                return {"content": text, "role": "assistant"}
            return {"content": "", "role": "assistant"}

    async def chat_with_tools(self, messages: List[Dict], tools: List[Dict] = None,
                               temperature: float = 0.7, max_tokens: int = 4096,
                               **kwargs) -> Dict:
        """Chat with function calling support."""
        system_instruction, contents = self._convert_messages_to_gemini(messages)
        gemini_tools = self._convert_tools_to_gemini(tools or [])

        url = f"{self.BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"
        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        if system_instruction:
            body["systemInstruction"] = system_instruction
        if gemini_tools:
            body["tools"] = gemini_tools

        session = await self._get_session()
        async with session.post(url, json=body) as resp:
            data = await resp.json()
            if "error" in data:
                raise Exception(f"Gemini API error: {data['error']['message']}")

            candidates = data.get("candidates", [])
            if not candidates:
                return {"content": "No response generated", "role": "assistant"}

            candidate = candidates[0]
            content_parts = candidate.get("content", {}).get("parts", [])

            # Check for function calls
            tool_calls = []
            text_content = ""

            for part in content_parts:
                if "text" in part:
                    text_content += part["text"]
                if "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append({
                        "id": f"call_{fc['name']}_{id(fc)}",
                        "type": "function",
                        "function": {
                            "name": fc["name"],
                            "arguments": json.dumps(fc.get("args", {}))
                        }
                    })

            result = {"content": text_content, "role": "assistant"}
            if tool_calls:
                result["tool_calls"] = tool_calls
            return result


class HuggingFaceClient:
    """
    HuggingFace Inference API client (free tier).
    - Uses Inference API for text generation
    - Supports models like Llama, Mistral, etc.
    - Function calling via structured output where supported
    """

    BASE_URL = "https://api-inference.huggingface.co/models"
    ROUTER_URL = "https://api-inference.huggingface.co/router"

    # Models that support function calling
    TOOL_MODELS = [
        "meta-llama/Llama-3.3-70B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
    ]

    # Models available on free tier
    FREE_MODELS = [
        "meta-llama/Llama-3.3-70B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "microsoft/DialoGPT-large",
        "google/gemma-2-2b-it",
        "HuggingFaceH4/zephyr-7b-beta",
    ]

    def __init__(self, token: str, model: str = "meta-llama/Llama-3.3-70B-Instruct"):
        self.token = token
        self.model = model
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.token}"}
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _build_tool_prompt(self, tools: List[Dict], messages: List[Dict]) -> str:
        """Build a prompt with tool descriptions for models that don't natively support function calling."""
        tool_descriptions = []
        for tool in tools:
            func = tool.get("function", {})
            tool_descriptions.append(
                f"- {func['name']}: {func.get('description', '')}\n"
                f"  Parameters: {json.dumps(func.get('parameters', {}))}"
            )

        system_prompt = """You are NovaMind, an AI agent with access to tools. 
When you need to use a tool, respond with a JSON block in this format:
```tool
{"name": "tool_name", "arguments": {"param": "value"}}
```

Available tools:
""" + "\n".join(tool_descriptions) + "\n\nAfter using a tool, you will receive the result and can continue."

        # Build conversation
        conversation = [system_prompt]
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                conversation.append(f"User: {content}")
            elif role == "assistant":
                conversation.append(f"Assistant: {content}")
            elif role == "tool":
                conversation.append(f"Tool Result: {content}")

        conversation.append("Assistant:")
        return "\n".join(conversation)

    def _parse_tool_calls(self, text: str) -> tuple:
        """Parse tool calls from model output."""
        import re

        # Look for ```tool ... ``` blocks
        tool_pattern = r'```tool\s*(\{.*?\})\s*```'
        matches = re.findall(tool_pattern, text, re.DOTALL)

        tool_calls = []
        for match in matches:
            try:
                data = json.loads(match)
                tool_calls.append({
                    "id": f"call_{data.get('name', 'unknown')}",
                    "type": "function",
                    "function": {
                        "name": data.get("name", ""),
                        "arguments": json.dumps(data.get("arguments", {}))
                    }
                })
            except json.JSONDecodeError:
                continue

        # Clean the text (remove tool blocks)
        clean_text = re.sub(tool_pattern, '', text).strip()
        return clean_text, tool_calls

    async def chat(self, messages: List[Dict], temperature: float = 0.7,
                   max_tokens: int = 4096, **kwargs) -> Dict:
        """Simple chat without tools."""
        # Convert to HF format
        formatted_messages = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ["system", "user", "assistant"]:
                formatted_messages.append({"role": role, "content": content})

        url = f"{self.BASE_URL}/{self.model}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        session = await self._get_session()
        try:
            async with session.post(url, json=body) as resp:
                data = await resp.json()

                if "error" in data:
                    # Fallback to non-chat API
                    return await self._chat_fallback(messages, temperature, max_tokens)

                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    return {"content": content, "role": "assistant"}
                return {"content": "", "role": "assistant"}
        except Exception as e:
            logger.error(f"HF API error: {e}")
            return await self._chat_fallback(messages, temperature, max_tokens)

    async def _chat_fallback(self, messages: List[Dict], temperature: float,
                              max_tokens: int) -> Dict:
        """Fallback using the basic text generation API."""
        prompt = "\n".join(
            f"{'System' if m['role']=='system' else m['role'].capitalize()}: {m['content']}"
            for m in messages
        )
        prompt += "\nAssistant:"

        url = f"{self.BASE_URL}/{self.model}"
        body = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": min(max_tokens, 2048),
                "temperature": max(temperature, 0.01),
                "return_full_text": False,
            }
        }

        session = await self._get_session()
        async with session.post(url, json=body) as resp:
            data = await resp.json()
            if isinstance(data, list) and data:
                text = data[0].get("generated_text", "")
                return {"content": text, "role": "assistant"}
            elif isinstance(data, dict) and "error" in data:
                return {"content": f"Error: {data['error']}", "role": "assistant"}
            return {"content": "", "role": "assistant"}

    async def chat_with_tools(self, messages: List[Dict], tools: List[Dict] = None,
                               temperature: float = 0.7, max_tokens: int = 4096,
                               **kwargs) -> Dict:
        """Chat with tool support via prompt engineering."""
        if not tools:
            return await self.chat(messages, temperature, max_tokens)

        # Build prompt with tool descriptions
        prompt_text = self._build_tool_prompt(tools, messages)

        url = f"{self.BASE_URL}/{self.model}/v1/chat/completions"
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt_text}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        session = await self._get_session()
        try:
            async with session.post(url, json=body) as resp:
                data = await resp.json()

                if "choices" in data:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    clean_text, tool_calls = self._parse_tool_calls(content)
                    result = {"content": clean_text, "role": "assistant"}
                    if tool_calls:
                        result["tool_calls"] = tool_calls
                    return result
                else:
                    # Fallback
                    return await self._tools_fallback(prompt_text, tools, temperature, max_tokens)
        except Exception as e:
            logger.error(f"HF tools error: {e}")
            return await self._tools_fallback(prompt_text, tools, temperature, max_tokens)

    async def _tools_fallback(self, prompt: str, tools: List[Dict],
                               temperature: float, max_tokens: int) -> Dict:
        """Fallback for tool calling."""
        url = f"{self.BASE_URL}/{self.model}"
        body = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": min(max_tokens, 2048),
                "temperature": max(temperature, 0.01),
                "return_full_text": False,
            }
        }

        session = await self._get_session()
        async with session.post(url, json=body) as resp:
            data = await resp.json()
            text = ""
            if isinstance(data, list) and data:
                text = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                text = data.get("generated_text", data.get("error", ""))

            clean_text, tool_calls = self._parse_tool_calls(text)
            result = {"content": clean_text, "role": "assistant"}
            if tool_calls:
                result["tool_calls"] = tool_calls
            return result

    async def check_model_status(self) -> Dict:
        """Check if the model is loaded and ready."""
        url = f"{self.BASE_URL}/{self.model}"
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return {"status": "ready", "model": self.model}
                data = await resp.json()
                return {"status": "loading", "model": self.model, "info": data}
        except Exception as e:
            return {"status": "error", "model": self.model, "error": str(e)}


class GroqClient:
    """
    Groq API client (free tier).
    - Ultra-fast inference on LPU hardware
    - OpenAI-compatible API format
    - Free tier: 30 requests/min, 1000 requests/day
    - Supports function calling natively
    
    Free models available:
    - llama-3.3-70b-versatile (latest Llama 3.3)
    - llama-3.1-8b-instant (fast, small)
    - mixtral-8x7b-32768 (large context)
    - gemma2-9b-it (Google Gemma)
    """

    BASE_URL = "https://api.groq.com/openai/v1"

    SUPPORTED_MODELS = [
        "openai/gpt-oss-120b",      # Latest - replaced llama-3.3-70b-versatile
        "openai/gpt-oss-20b",       # Fast - replaced llama-3.1-8b-instant
        # "qwen/qwen3.6-27b"        # Preview - for future multimodal needs
    ]

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model = model
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def chat(self, messages: List[Dict], temperature: float = 0.7,
                   max_tokens: int = 4096, reasoning_effort: str = "low",
                   **kwargs) -> Dict:
        """Simple chat without tools using OpenAI-compatible format."""
        url = f"{self.BASE_URL}/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
        }

        session = await self._get_session()
        try:
            async with session.post(url, json=body) as resp:
                data = await resp.json()

                if "error" in data:
                    error_msg = data["error"].get("message", str(data["error"]))
                    raise Exception(f"Groq API error: {error_msg}")

                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    return {"content": content, "role": "assistant"}
                return {"content": "", "role": "assistant"}
        except aiohttp.ClientError as e:
            raise Exception(f"Groq connection error: {e}")

    async def chat_with_tools(self, messages: List[Dict], tools: List[Dict] = None,
                               temperature: float = 0.7, max_tokens: int = 4096,
                               reasoning_effort: str = "low", **kwargs) -> Dict:
        """Chat with native function calling support (OpenAI-compatible)."""
        url = f"{self.BASE_URL}/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
        }

        # Add tools if provided (OpenAI format - Groq is compatible)
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        session = await self._get_session()
        try:
            async with session.post(url, json=body) as resp:
                data = await resp.json()

                if "error" in data:
                    error_msg = data["error"].get("message", str(data["error"]))
                    raise Exception(f"Groq API error: {error_msg}")

                choices = data.get("choices", [])
                if not choices:
                    return {"content": "No response generated", "role": "assistant"}

                message = choices[0].get("message", {})
                result = {
                    "content": message.get("content", ""),
                    "role": "assistant"
                }

                # Check for tool calls (native OpenAI format)
                if "tool_calls" in message and message["tool_calls"]:
                    tool_calls = []
                    for tc in message["tool_calls"]:
                        tool_calls.append({
                            "id": tc.get("id", f"call_{tc['function']['name']}"),
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"].get("arguments", "{}")
                            }
                        })
                    result["tool_calls"] = tool_calls

                # Add usage info if available
                if "usage" in data:
                    result["usage"] = data["usage"]

                return result
        except aiohttp.ClientError as e:
            raise Exception(f"Groq connection error: {e}")


class LLMRouter:
    """
    Routes between Gemini, Groq, and HuggingFace based on availability and task.
    Provides a unified interface for the agent with automatic failover.
    
    Features:
    - Automatic fallback chain: Primary → Secondary → Tertiary
    - Circuit breaker for each provider (prevents cascading failures)
    - Configurable primary provider
    
    Circuit Breaker States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Provider failing, requests skip this provider
    - HALF_OPEN: Testing recovery, one request allowed through
    """

    def __init__(self, gemini_key: Optional[str] = None, groq_key: Optional[str] = None,
                 hf_token: Optional[str] = None, primary: str = "gemini",
                 gemini_model: str = "gemini-2.0-flash",
                 groq_model: str = "openai/gpt-oss-20b",
                 hf_model: str = "meta-llama/Llama-3.3-70B-Instruct"):
        from core.agent_safety import CircuitBreaker
        
        self.primary = primary
        self.gemini: Optional[GeminiClient] = None
        self.groq: Optional[GroqClient] = None
        self.huggingface: Optional[HuggingFaceClient] = None

        # Initialize circuit breakers for each provider
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        if gemini_key:
            self.gemini = GeminiClient(gemini_key, gemini_model)
            self.circuit_breakers["gemini"] = CircuitBreaker(name="gemini")
        if groq_key:
            self.groq = GroqClient(groq_key, groq_model)
            self.circuit_breakers["groq"] = CircuitBreaker(name="groq")
        if hf_token:
            self.huggingface = HuggingFaceClient(hf_token, hf_model)
            self.circuit_breakers["huggingface"] = CircuitBreaker(name="huggingface")

    def _get_fallback_chain(self) -> List[tuple]:
        """Get the ordered fallback chain based on primary provider."""
        chain = []
        
        # Primary first
        if self.primary == "gemini" and self.gemini:
            chain.append(("gemini", self.gemini))
        elif self.primary == "groq" and self.groq:
            chain.append(("groq", self.groq))
        elif self.primary == "huggingface" and self.huggingface:
            chain.append(("huggingface", self.huggingface))
        
        # Then fallbacks in order: Gemini → Groq → HuggingFace
        for name, client in [
            ("gemini", self.gemini),
            ("groq", self.groq),
            ("huggingface", self.huggingface),
        ]:
            if client and (name, client) not in chain:
                chain.append((name, client))
        
        return chain

    async def chat(self, messages: List[Dict], **kwargs) -> Dict:
        """
        Send a chat request, falling back through providers.
        Uses circuit breaker to skip failing providers.
        """
        chain = self._get_fallback_chain()
        
        if not chain:
            raise Exception("No LLM client configured")
        
        last_error = None
        for name, client in chain:
            # Check circuit breaker - skip if circuit is open
            breaker = self.circuit_breakers.get(name)
            if breaker and not breaker.can_execute():
                logger.info(f"Circuit breaker for {name} is OPEN, skipping provider")
                continue
            
            try:
                result = await client.chat(messages, **kwargs)
                # Record success
                if breaker:
                    breaker.record_success()
                return result
            except Exception as e:
                last_error = e
                # Record failure
                if breaker:
                    breaker.record_failure()
                logger.warning(f"{name} failed, trying next provider: {e}")
                continue
        
        raise Exception(f"All LLM providers failed. Last error: {last_error}")

    async def chat_with_tools(self, messages: List[Dict], tools: List[Dict] = None,
                               **kwargs) -> Dict:
        """
        Send a chat request with tools, falling back through providers.
        Uses circuit breaker to skip failing providers.
        """
        chain = self._get_fallback_chain()
        
        if not chain:
            raise Exception("No LLM client configured")
        
        last_error = None
        for name, client in chain:
            # Check circuit breaker - skip if circuit is open
            breaker = self.circuit_breakers.get(name)
            if breaker and not breaker.can_execute():
                logger.info(f"Circuit breaker for {name} is OPEN, skipping provider")
                continue
            
            try:
                result = await client.chat_with_tools(messages, tools, **kwargs)
                # Record success
                if breaker:
                    breaker.record_success()
                return result
            except Exception as e:
                last_error = e
                # Record failure
                if breaker:
                    breaker.record_failure()
                logger.warning(f"{name} tools failed, trying next provider: {e}")
                continue
        
        raise Exception(f"All LLM providers failed. Last error: {last_error}")

    async def close(self):
        if self.gemini:
            await self.gemini.close()
        if self.groq:
            await self.groq.close()
        if self.huggingface:
            await self.huggingface.close()

    def get_status(self) -> Dict:
        """Get router status including circuit breaker states."""
        status = {
            "primary": self.primary,
            "gemini_configured": self.gemini is not None,
            "gemini_model": self.gemini.model if self.gemini else None,
            "groq_configured": self.groq is not None,
            "groq_model": self.groq.model if self.groq else None,
            "huggingface_configured": self.huggingface is not None,
            "huggingface_model": self.huggingface.model if self.huggingface else None,
            "fallback_chain": [name for name, _ in self._get_fallback_chain()],
            "circuit_breakers": {}
        }
        
        # Add circuit breaker status
        for name, breaker in self.circuit_breakers.items():
            status["circuit_breakers"][name] = breaker.get_status()
        
        return status
