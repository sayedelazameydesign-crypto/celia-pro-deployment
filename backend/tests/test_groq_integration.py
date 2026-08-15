"""
Groq Integration Smoke Test
============================

اختبار حقيقي لـ Groq API - بيتصل بـ API فعلياً ويتأكد إن الموديلات شغالة.

عشان تشغل الاختبار ده:
    export GROQ_API_KEY="gsk_..."
    pytest tests/test_groq_integration.py -v

لو مفيش GROQ_API_KEY، الاختبار هيتعمله skip.
"""

import pytest
import os
from typing import Dict, Any


# اختياري: لو GROQ_API_KEY مش موجود، نتخطى كل الاختبارات
pytestmark = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY environment variable not set - skipping real API tests"
)


@pytest.fixture
def groq_api_key() -> str:
    """Get Groq API key from environment"""
    return os.getenv("GROQ_API_KEY", "")


@pytest.fixture
async def groq_client(groq_api_key):
    """Create real Groq client"""
    from core.llm_clients import GroqClient
    client = GroqClient(api_key=groq_api_key, model="openai/gpt-oss-20b")
    yield client
    await client.close()


class TestGroqSmokeTest:
    """اختبارات حقيقية لـ Groq API"""
    
    @pytest.mark.asyncio
    async def test_groq_api_connectivity(self, groq_client):
        """
        Smoke Test #1: Basic connectivity
        نتأكد إن Groq API بترد أصلاً
        """
        messages = [{"role": "user", "content": "Say 'ok' only"}]
        
        response = await groq_client.chat(
            messages=messages,
            temperature=0.1,
            max_tokens=10
        )
        
        assert response is not None
        assert "content" in response
        assert len(response["content"]) > 0
        print(f"\n✅ Groq API connectivity: {response['content'][:50]}")
    
    @pytest.mark.asyncio
    async def test_groq_model_openai_gpt_oss_120b(self, groq_api_key):
        """
        Smoke Test #2: openai/gpt-oss-120b model
        نتأكد إن الموديل ده شغال فعلاً
        """
        from core.llm_clients import GroqClient
        
        client = GroqClient(api_key=groq_api_key, model="openai/gpt-oss-120b")
        
        try:
            messages = [{"role": "user", "content": "Say 'ok' only"}]
            
            response = await client.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=10,
                reasoning_effort="low"
            )
            
            assert response is not None
            assert "content" in response
            assert len(response["content"]) > 0
            print(f"\n✅ openai/gpt-oss-120b: {response['content'][:50]}")
        
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_groq_model_openai_gpt_oss_20b(self, groq_api_key):
        """
        Smoke Test #3: openai/gpt-oss-20b model
        نتأكد إن الموديل ده شغال فعلاً
        """
        from core.llm_clients import GroqClient
        
        client = GroqClient(api_key=groq_api_key, model="openai/gpt-oss-20b")
        
        try:
            messages = [{"role": "user", "content": "Say 'ok' only"}]
            
            response = await client.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=10,
                reasoning_effort="low"
            )
            
            assert response is not None
            assert "content" in response
            assert len(response["content"]) > 0
            print(f"\n✅ openai/gpt-oss-20b: {response['content'][:50]}")
        
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_groq_function_calling(self, groq_api_key):
        """
        Smoke Test #4: Function calling
        نتأكد إن function calling شغال مع الموديلات الجديدة
        """
        from core.llm_clients import GroqClient
        
        client = GroqClient(api_key=groq_api_key, model="openai/gpt-oss-20b")
        
        try:
            messages = [
                {"role": "user", "content": "Call the test_tool function"}
            ]
            
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "description": "A test function",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "param1": {
                                    "type": "string",
                                    "description": "Test parameter"
                                }
                            },
                            "required": ["param1"]
                        }
                    }
                }
            ]
            
            response = await client.chat_with_tools(
                messages=messages,
                tools=tools,
                temperature=0.1,
                max_tokens=100,
                reasoning_effort="low"
            )
            
            assert response is not None
            
            # إما content أو tool_calls لازم يكون موجود
            has_content = response.get("content") and len(response["content"]) > 0
            has_tool_calls = "tool_calls" in response and len(response["tool_calls"]) > 0
            
            assert has_content or has_tool_calls, "Response must have either content or tool_calls"
            
            if has_tool_calls:
                print(f"\n✅ Function calling works: {response['tool_calls'][0]['function']['name']}")
            else:
                print(f"\n✅ Function calling (content fallback): {response['content'][:50]}")
        
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_groq_reasoning_effort_low(self, groq_api_key):
        """
        Smoke Test #5: reasoning_effort parameter
        نتأكد إن الـ parameter ده شغال ومش بيرمي error
        """
        from core.llm_clients import GroqClient
        
        client = GroqClient(api_key=groq_api_key, model="openai/gpt-oss-20b")
        
        try:
            messages = [{"role": "user", "content": "Say 'ok' only"}]
            
            # جرب القيم المختلفة لـ reasoning_effort
            for effort in ["low", "medium", "high"]:
                response = await client.chat(
                    messages=messages,
                    temperature=0.1,
                    max_tokens=10,
                    reasoning_effort=effort
                )
                
                assert response is not None
                assert "content" in response
            
            print(f"\n✅ reasoning_effort parameter works for all values")
        
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_groq_fallback_chain(self, groq_api_key):
        """
        Smoke Test #6: Fallback chain
        نتأكد إن LLMRouter شغال مع Groq في الـ fallback chain
        """
        from core.llm_clients import LLMRouter
        
        router = LLMRouter(
            groq_key=groq_api_key,
            primary="groq",
            groq_model="openai/gpt-oss-20b"
        )
        
        try:
            messages = [{"role": "user", "content": "Say 'ok' only"}]
            
            response = await router.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=10,
                reasoning_effort="low"
            )
            
            assert response is not None
            assert "content" in response
            assert len(response["content"]) > 0
            
            print(f"\n✅ LLMRouter with Groq fallback: {response['content'][:50]}")
        
        finally:
            await router.close()


class TestGroqLatency:
    """اختبارات الأداء - بتقيس latency"""
    
    @pytest.mark.asyncio
    async def test_groq_response_time(self, groq_api_key):
        """
        Performance Test: Response time
        نتأكد إن الـ response time معقول
        """
        from core.llm_clients import GroqClient
        import time
        
        client = GroqClient(api_key=groq_api_key, model="openai/gpt-oss-20b")
        
        try:
            messages = [{"role": "user", "content": "Say 'ok' only"}]
            
            start_time = time.time()
            
            response = await client.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=10,
                reasoning_effort="low"
            )
            
            elapsed_time = time.time() - start_time
            
            assert response is not None
            assert elapsed_time < 10.0, f"Response took too long: {elapsed_time:.2f}s"
            
            print(f"\n⚡ Response time: {elapsed_time:.2f}s")
        
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_groq_reasoning_effort_impact(self, groq_api_key):
        """
        Performance Test: reasoning_effort impact on latency
        نقارن latency بين low و high
        """
        from core.llm_clients import GroqClient
        import time
        
        client = GroqClient(api_key=groq_api_key, model="openai/gpt-oss-20b")
        
        try:
            messages = [{"role": "user", "content": "Say 'ok' only"}]
            
            # قياس latency مع low
            start_time = time.time()
            await client.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=10,
                reasoning_effort="low"
            )
            low_latency = time.time() - start_time
            
            # قياس latency مع high
            start_time = time.time()
            await client.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=10,
                reasoning_effort="high"
            )
            high_latency = time.time() - start_time
            
            print(f"\n⚡ Latency comparison:")
            print(f"   reasoning_effort=low:  {low_latency:.2f}s")
            print(f"   reasoning_effort=high: {high_latency:.2f}s")
            
            if high_latency > low_latency:
                print(f"   📊 High is {high_latency/low_latency:.1f}x slower")
        
        finally:
            await client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
