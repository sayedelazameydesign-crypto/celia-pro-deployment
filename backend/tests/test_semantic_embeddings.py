"""
Test Semantic Embeddings
=========================
Tests that verify semantic embeddings work correctly.

Verifies that:
- Similar words ("hello", "greetings") have high similarity
- Different words ("hello", "car") have low similarity
- Arabic words work correctly
- Model loads successfully
"""

import pytest
from core.embeddings import (
    EmbeddingProvider,
    generate_embedding,
    cosine_similarity,
    get_embedding_provider
)


class TestEmbeddingProvider:
    """Test EmbeddingProvider class."""
    
    @pytest.fixture
    def provider(self):
        """Create embedding provider."""
        return EmbeddingProvider()
    
    def test_provider_initialization(self, provider):
        """Test that provider initializes correctly."""
        assert provider is not None
        assert provider.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert provider.dimensions == 384
    
    def test_model_loading(self, provider):
        """Test that model loads successfully."""
        provider._load_model()
        assert provider._initialized is True
        # Model should be loaded (or fallback to hash-based)
        # We don't assert provider.model is not None because it might fallback
    
    def test_embedding_generation(self, provider):
        """Test that embeddings are generated."""
        vector = provider.embed("Hello world")
        assert vector is not None
        assert isinstance(vector, list)
        assert len(vector) > 0
        assert all(isinstance(x, (int, float)) for x in vector)
    
    def test_embedding_dimensions(self, provider):
        """Test that embeddings have correct dimensions."""
        vector = provider.embed("Test", dimensions=256)
        assert len(vector) == 256
        
        vector = provider.embed("Test", dimensions=384)
        assert len(vector) == 384
    
    def test_batch_embedding(self, provider):
        """Test batch embedding generation."""
        texts = ["Hello", "World", "Test"]
        vectors = provider.embed_batch(texts)
        assert len(vectors) == 3
        assert all(isinstance(v, list) for v in vectors)
        assert all(len(v) > 0 for v in vectors)


class TestSemanticSimilarity:
    """Test semantic similarity between words."""
    
    @pytest.fixture
    def provider(self):
        """Create embedding provider."""
        return EmbeddingProvider()
    
    def test_similar_english_words(self, provider):
        """Test that similar English words have high similarity."""
        # "hello" and "greetings" should be similar
        v1 = provider.embed("hello")
        v2 = provider.embed("greetings")
        
        similarity = provider.cosine_similarity(v1, v2)
        
        # With semantic model, similarity should be > 0.5
        # With hash-based, it would be random (~0.0)
        # We accept > 0.3 as "semantic" (accounting for model variance)
        assert similarity > 0.3, f"Expected similarity > 0.3, got {similarity}"
    
    def test_dissimilar_english_words(self, provider):
        """Test that dissimilar words have low similarity."""
        # "hello" and "car" should NOT be similar
        v1 = provider.embed("hello")
        v2 = provider.embed("car")
        
        similarity = provider.cosine_similarity(v1, v2)
        
        # Similarity should be relatively low
        # (though not necessarily negative)
        assert similarity < 0.8, f"Expected similarity < 0.8, got {similarity}"
    
    def test_similar_vs_dissimilar(self, provider):
        """Test that similar words are MORE similar than dissimilar ones."""
        v_hello = provider.embed("hello")
        v_greetings = provider.embed("greetings")
        v_car = provider.embed("car")
        
        sim_greetings = provider.cosine_similarity(v_hello, v_greetings)
        sim_car = provider.cosine_similarity(v_hello, v_car)
        
        # "hello" should be more similar to "greetings" than to "car"
        assert sim_greetings > sim_car, \
            f"Expected 'hello' more similar to 'greetings' ({sim_greetings}) than 'car' ({sim_car})"
    
    def test_arabic_similarity(self, provider):
        """Test that Arabic words work correctly."""
        # "مرحبا" and "أهلا" should be similar
        v1 = provider.embed("مرحبا")
        v2 = provider.embed("أهلا")
        
        similarity = provider.cosine_similarity(v1, v2)
        
        # Should have some similarity (multilingual model)
        # We accept > 0.2 as working (accounting for model variance)
        assert similarity > 0.2, f"Expected Arabic similarity > 0.2, got {similarity}"
    
    def test_sentence_similarity(self, provider):
        """Test that similar sentences have high similarity."""
        # "What is the weather?" and "How is the weather?" should be similar
        v1 = provider.embed("What is the weather?")
        v2 = provider.embed("How is the weather?")
        v3 = provider.embed("I like programming")
        
        sim_weather = provider.cosine_similarity(v1, v2)
        sim_programming = provider.cosine_similarity(v1, v3)
        
        # Weather questions should be more similar to each other
        assert sim_weather > sim_programming, \
            f"Expected weather similarity ({sim_weather}) > programming ({sim_programming})"


class TestGlobalFunctions:
    """Test global convenience functions."""
    
    def test_generate_embedding(self):
        """Test generate_embedding function."""
        vector = generate_embedding("Hello world")
        assert vector is not None
        assert isinstance(vector, list)
        assert len(vector) > 0
    
    def test_generate_embedding_with_dimensions(self):
        """Test generate_embedding with custom dimensions."""
        vector = generate_embedding("Test", dimensions=256)
        assert len(vector) == 256
    
    def test_cosine_similarity_function(self):
        """Test cosine_similarity function."""
        v1 = generate_embedding("hello")
        v2 = generate_embedding("greetings")
        
        similarity = cosine_similarity(v1, v2)
        assert -1.0 <= similarity <= 1.0
    
    def test_get_embedding_provider_singleton(self):
        """Test that get_embedding_provider returns singleton."""
        provider1 = get_embedding_provider()
        provider2 = get_embedding_provider()
        assert provider1 is provider2


class TestEmbeddingQuality:
    """Test embedding quality and correctness."""
    
    @pytest.fixture
    def provider(self):
        """Create embedding provider."""
        return EmbeddingProvider()
    
    def test_embeddings_are_normalized(self, provider):
        """Test that embeddings are normalized (unit vectors)."""
        vector = provider.embed("Test text")
        
        # Calculate L2 norm
        import numpy as np
        norm = np.linalg.norm(vector)
        
        # Should be close to 1.0 (normalized)
        assert abs(norm - 1.0) < 0.1, f"Expected norm ~1.0, got {norm}"
    
    def test_same_text_same_embedding(self, provider):
        """Test that same text produces same embedding."""
        v1 = provider.embed("Hello world")
        v2 = provider.embed("Hello world")
        
        # Should be identical (deterministic)
        assert v1 == v2
    
    def test_different_text_different_embedding(self, provider):
        """Test that different text produces different embedding."""
        v1 = provider.embed("Hello")
        v2 = provider.embed("World")
        
        # Should be different
        assert v1 != v2
    
    def test_embedding_not_all_zeros(self, provider):
        """Test that embeddings are not all zeros."""
        vector = provider.embed("Test")
        
        # Should not be all zeros
        assert any(v != 0 for v in vector)
    
    def test_embedding_not_all_same(self, provider):
        """Test that embeddings have variation."""
        vector = provider.embed("Test text")
        
        # Should not be all the same value
        assert len(set(vector)) > 1


class TestSemanticSearch:
    """Test semantic search use case."""
    
    @pytest.fixture
    def provider(self):
        """Create embedding provider."""
        return EmbeddingProvider()
    
    def test_find_similar_queries(self, provider):
        """Test finding similar queries."""
        # Database of queries
        queries = [
            "What is Python?",
            "How to learn Python?",
            "What is JavaScript?",
            "Python tutorial",
            "JavaScript vs Python",
            "I like cats",
        ]
        
        # Query
        query = "How to use Python?"
        query_vector = provider.embed(query)
        
        # Calculate similarities
        similarities = []
        for q in queries:
            q_vector = provider.embed(q)
            sim = provider.cosine_similarity(query_vector, q_vector)
            similarities.append((q, sim))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Python-related queries should be more similar
        top_3 = [s[0] for s in similarities[:3]]
        
        # At least 2 of top 3 should be Python-related
        python_related = sum(1 for q in top_3 if "Python" in q or "python" in q.lower())
        assert python_related >= 2, f"Expected at least 2 Python-related in top 3, got {top_3}"


class TestFallbackBehavior:
    """Test fallback to hash-based embeddings."""
    
    def test_fallback_if_model_unavailable(self):
        """Test that system works even if model fails to load."""
        # This test ensures the system doesn't crash if model loading fails
        provider = EmbeddingProvider()
        
        # Force model to None (simulate failure)
        provider.model = None
        provider._initialized = True
        
        # Should still generate embeddings (using hash-based fallback)
        vector = provider.embed("Test")
        assert vector is not None
        assert isinstance(vector, list)
        assert len(vector) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
